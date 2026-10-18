#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка мода замены текстур существ для Heroes of Might and Magic V 3.1
(Tribes of the East / «Повелители Орды»).

Что делает скрипт:
  1. Достаёт оригинальный data.pak из многотомного архива data.z01..data.z18 + data.zip
     (либо берёт готовый data.pak, если он лежит рядом / передан аргументом).
  2. Для каждой PNG из папки «Текстуры» находит соответствующий игровой .dds
     (сопоставление выполнено по UV-раскладке атласа, см. MAPPING ниже и README.md).
  3. Перекодирует PNG обратно в DDS: тот же размер, тот же формат (DXT1/DXT3),
     то же число mip-уровней, что у оригинала. Альфа-канал берётся из ОРИГИНАЛЬНОЙ
     текстуры (в PNG его нет) — иначе «_add»-текстуры и прозрачные края крыльев/плащей
     превратились бы в непрозрачные прямоугольники.
  4. Упаковывает результат в zz_CreatureTextures_H5_3.1.pak — обычный ZIP,
     именно в таком виде HoMM5 подхватывает моды из папки data.

Использование:
    python3 build_mod.py [путь_к_data.pak]
Требуются: pillow, numpy  (pip install pillow numpy)
"""
import io
import os
import struct
import sys
import zipfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "Текстуры")
OUT_H5U = os.path.join(ROOT, "CreatureTextures_H5_3.1.h5u")
OUT_PAK = os.path.join(ROOT, "zz_CreatureTextures_H5_3.1.pak")
# ВАЖНО: HoMM5 при одинаковых путях в разных архивах берёт файл с САМОЙ НОВОЙ
# датой внутри архива. У оригиналов data.pak даты 2007 года, поэтому все записи
# мода датируем заведомо позже, иначе игра молча возьмёт оригинальные текстуры.
ENTRY_DATE = (2026, 10, 19, 12, 0, 0)

# ---------------------------------------------------------------------------
# PNG из папки «Текстуры»  ->  игровые .dds, которые она заменяет.
# У большинства существ одна и та же картинка лежит в data.pak дважды:
# основная текстура (512) и LOD-версия (256) для дальних планов — заменяем обе,
# иначе на отдалении существо «переодевалось» бы обратно в оригинал.
# ---------------------------------------------------------------------------
MAPPING = {
    # Оплот (Haven): Крестьянин
    "1792341709661-01a14fe3-6ab6-7874-bfc2-5ccd1e6e1bb1.png": [
        "Textures/auto-imported_______320/dev/Test/TMPcharacters/Peasant/Peasant.tga.dds",
        "_(Model)/Creatures/Haven/Peasant_LOD-Peasant_LOD.(Texture).dds",
    ],
    # Лесной союз (Sylvan): Фея (Pixie), основная текстура
    "1792354047166-01a1509f-bc75-7f12-9009-e67265b4a41d.png": [
        "Textures/auto-imported/Creatures/Preserve/Pixie_LOD/Pixie.tga.dds",
        "_(Model)/Creatures/Preserve/Pixie_LOD-Pixie_LOD.(Texture).dds",
    ],
    # Лесной союз: Фея, доп. текстура (волосы/крылья, _add)
    # В папке лежат ДВА варианта этой текстуры (…1792354305719… и …1792354571328…,
    # почти одинаковые перегенерации одной картинки). В мод взят первый;
    # чтобы поставить второй — поменяйте имя файла здесь и пересоберите мод.
    "1792354305719-01a150a3-c764-7751-a615-5ed3eec5fa83.png": [
        "Textures/auto-imported/Creatures/Preserve/Pixie_LOD/Pixie_add.tga.dds",
        "_(Model)/Creatures/Preserve/Pixie_LOD-Pixie_add_LOD.(Texture).dds",
    ],
    # Лесной союз: Дриада/Спрайт (Spirit), доп. текстура (волосы с цветами, _add)
    "1792354765714-01a150aa-d7ae-7a46-aeff-991c9fffc709.png": [
        "Textures/auto-imported/Creatures/Preserve/Spirit_LOD/Spirit_add.tga.dds",
        "_(Model)/Creatures/Preserve/Spirit_LOD-Spirit_add_LOD.(Texture).dds",
    ],
    # Лесной союз: Дриада/Спрайт (Spirit), основная текстура
    "1792355199042-01a150b1-4bba-72a7-8e4e-24cc49e24e67.png": [
        "Textures/auto-imported/Creatures/Preserve/Spirit_LOD/Spirit.tga.dds",
        "_(Model)/Creatures/Preserve/Spirit_LOD-Spirit_LOD.(Texture).dds",
    ],
    # Лесной союз: Эльфийский лучник (Wood Elf)
    "1792355720493-01a150b9-2c13-7c30-af61-3ccd32857359.png": [
        "Textures/WoodElf/WoodElf.tga.dds",
        "_(Model)/Creatures/Preserve/WoodElf_LOD-WoodElf_LOD.(Texture).dds",
    ],
    # Лесной союз: Высший эльф (High Elf)
    "1792355850358-01a150bb-1595-7588-9392-47d29212aadd.png": [
        "Textures/HighElf/HighElf.tga.dds",
        "_(Model)/Creatures/Preserve/HighElf_LOD-HighElf_LOD.(Texture).dds",
    ],
    # Некрополис: Демилич (Demi Lich), основная текстура
    "1792356401071-01a150c3-6b07-7cc8-8917-45959fc563c0.png": [
        "Textures/auto-imported_____18951/Creatures/Necropolis/DemiLich/DemiLich.tga.dds",
        "_(Model)/Creatures/Necropolis/DemilLch_LOD-DemiLich_LOD.(Texture).dds",
    ],
    # Некрополис: Владыка личей (Lich Master, альт. апгрейд), основная текстура
    "1792356663260-01a150c7-a797-759c-947c-0b9b4e750eb1.png": [
        "Characters/Creatures/Necropolis/AlternativeUpgrade/LichMaster-LichUP2.(Texture).dds",
    ],
    # Некрополис: Владыка личей, доп. текстура (_add, посох/рука/топор)
    "1792356722745-01a150c8-ac2e-7076-9dbe-85c7ea43d6c4.png": [
        "Characters/Creatures/Necropolis/AlternativeUpgrade/LichMaster-LichUP2_add.(Texture).dds",
    ],
    # Крепость (Fortress, гномы): Копейщик (Spear Fighter), тело
    "1792357127207-01a150ce-a06f-7cdf-b430-c91ca5b1df5d.png": [
        "Characters/Creatures/Dwarves/T2_Dwarf/SpearFighter-SpearFighter_Body.(Texture).dds",
    ],
    # Крепость: Копейщик, металл (доспех/оружие)
    "1792357203720-01a150cf-dae3-7365-9130-1131a60868f3.png": [
        "Characters/Creatures/Dwarves/T2_Dwarf/SpearFighter-SpearFighter_Metal.(Texture).dds",
    ],
    # Крепость: Защитник (Defender), металл
    "1792357436369-01a150d3-8b0b-764a-abcc-0b11ef3c7d9b.png": [
        "Characters/Creatures/Dwarves/T1_Dwarf/Defender-Defender_Metall.(Texture).dds",
        "Characters/Creatures/Dwarves/T1_Dwarf/Defender_LOD-Defender_Metall_LOD.(Texture).dds",
    ],
    # Крепость: Защитник, тело
    "1792357483268-01a150d4-3aa4-7da0-85e5-323b9b0aaf5e.png": [
        "Characters/Creatures/Dwarves/T1_Dwarf/Defender-Defender_body.(Texture).dds",
        "Characters/Creatures/Dwarves/T1_Dwarf/Defender_LOD-Defender_body_LOD.(Texture).dds",
    ],
    # Лесной союз: Друид (Druid), основная текстура
    "1792357706709-01a150d7-951c-7eb1-a1c9-aa8ca6ef634a.png": [
        "Textures/Preserve_____11264/Druid/Druid.tga.dds",
        "_(Model)/Creatures/Preserve/Druid_LOD-Druid_LOD.(Texture).dds",
    ],
    # Лесной союз: Друид, доп. текстура (_add, плащ/посох)
    "1792357767481-01a150d8-6d91-78e2-ad24-24f56273f35c.png": [
        "Textures/Preserve_____11264/Druid/Druid_add.tga.dds",
        "_(Model)/Creatures/Preserve/Druid_LOD-Druid_add_LOD.(Texture).dds",
    ],
    # Инферно: Балор (Balor / Пит-лорд), основная текстура
    "1792358418659-01a150e2-3998-71fd-8849-33a7a226a788.png": [
        "Textures/Creatures/Inferno/Pitfiend/Balor/balor.tga.dds",
        "_(Model)/Creatures/Inferno/Balor_LOD.dds",
    ],
    # Инферно: Балор, меч
    "1792358478484-01a150e3-2779-7fe0-b5e0-59af9eb04d94.png": [
        "Textures/Creatures/Inferno/Pitfiend/Balor/balor_sword.tga.dds",
        "_(Model)/Creatures/Inferno/Balor_LOD-balor_sword_LOD.(Texture).dds",
    ],
}

# ---------------------------------------------------------------------------
# DDS: чтение заголовка оригинала и кодирование DXT1 / DXT3 (BC1 / BC2)
# ---------------------------------------------------------------------------

def rgb565(c):
    r, g, b = (int(round(float(x))) for x in c[:3])
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def from565(v):
    r = ((v >> 11) & 31) * 255 // 31
    g = ((v >> 5) & 63) * 255 // 63
    b = (v & 31) * 255 // 31
    return np.array([r, g, b], dtype=np.float32)


def encode_color_block(px):
    """px: (16,3) float 0..255 -> 8 байт BC1 (4-цветный режим, c0>c1)."""
    lo = px.min(axis=0)
    hi = px.max(axis=0)
    # inset endpoints (классический приём — меньше ошибка квантования)
    inset = (hi - lo) * (1.0 / 16.0)
    c0c, c1c = hi - inset, lo + inset
    c0, c1 = rgb565(c0c), rgb565(c1c)
    if c0 < c1:
        c0, c1, c0c, c1c = c1, c0, c1c, c0c
    if c0 == c1:  # одноцветный блок
        return struct.pack("<HHI", c0, c1, 0)
    p0, p1 = from565(c0), from565(c1)
    palette = np.stack([p0, p1, (2 * p0 + p1) / 3.0, (p0 + 2 * p1) / 3.0])
    dist = ((px[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)
    idx = dist.argmin(axis=1)
    bits = 0
    for i, v in enumerate(idx):
        bits |= int(v) << (2 * i)
    return struct.pack("<HHI", c0, c1, bits)


def encode_dds(rgba_img, fourcc, n_mips, header128):
    """PIL RGBA image -> DDS bytes. Заголовок (первые 128 байт) копируем из
    оригинального файла игры один в один — движок привередлив к флагам,
    а размер/формат/mip-число у нас и так совпадают с оригиналом."""
    out = bytearray(header128)
    assert out[:4] == b"DDS " and out[84:88] == fourcc
    img = rgba_img
    for level in range(n_mips):
        lw, lh = img.size
        arr = np.asarray(img, dtype=np.float32)
        bw, bh = max(1, (lw + 3) // 4), max(1, (lh + 3) // 4)
        # дополняем края до кратности 4 повторением крайних пикселей
        pad = np.zeros((bh * 4, bw * 4, 4), dtype=np.float32)
        pad[:lh, :lw] = arr
        if lw < bw * 4:
            pad[:lh, lw:] = arr[:, -1:]
        if lh < bh * 4:
            pad[lh:, :] = pad[lh - 1:lh, :]
        blocks = pad.reshape(bh, 4, bw, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
        for blk in blocks:
            if fourcc == b"DXT3":  # явная 4-битная альфа
                a = np.clip(np.round(blk[:, 3] / 17.0), 0, 15).astype(np.uint64)
                packed = 0
                for i, v in enumerate(a):
                    packed |= int(v) << (4 * i)
                out += struct.pack("<Q", packed)
            out += encode_color_block(blk[:, :3])
        if lw == 1 and lh == 1:
            break
        img = img.resize((max(1, lw // 2), max(1, lh // 2)), Image.LANCZOS)
    return bytes(out)


def parse_dds_header(data):
    assert data[:4] == b"DDS ", "не DDS"
    h, w = struct.unpack("<II", data[12:20])
    mips = struct.unpack("<I", data[28:32])[0]
    return w, h, data[84:88], max(1, mips)


# ---------------------------------------------------------------------------

def open_data_pak():
    """Возвращает ZipFile с содержимым data.pak (ищет рядом с собой)."""
    if len(sys.argv) > 1:
        return zipfile.ZipFile(sys.argv[1])
    plain = os.path.join(ROOT, "data.pak")
    if os.path.exists(plain):
        return zipfile.ZipFile(plain)
    # многотомный архив: data.z01..data.zNN + data.zip -> склеить и достать data.pak
    parts = sorted(
        f for f in os.listdir(ROOT)
        if f.startswith("data.z") and not f.endswith(".zip")
    ) + ["data.zip"]
    blob = io.BytesIO()
    for p in parts:
        with open(os.path.join(ROOT, p), "rb") as fh:
            blob.write(fh.read())
    blob.seek(0)
    outer = zipfile.ZipFile(blob)
    return zipfile.ZipFile(io.BytesIO(outer.read("data.pak")))


def writestr_new(zout, arcname, data):
    """Запись в архив с датой ENTRY_DATE (см. комментарий к ENTRY_DATE)."""
    info = zipfile.ZipInfo(arcname, date_time=ENTRY_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zout.writestr(info, data)


def build(pak):
    """Возвращает dict {путь_в_архиве: байты} со всем содержимым мода."""
    files = {}
    for png_name, targets in MAPPING.items():
        png_path = os.path.join(SRC_DIR, png_name)
        new_rgb = Image.open(png_path).convert("RGB")
        for target in targets:
            orig_bytes = pak.read(target)
            w, h, fourcc, n_mips = parse_dds_header(orig_bytes)
            orig = Image.open(io.BytesIO(orig_bytes)).convert("RGBA")
            # новая картинка в исходном разрешении + ОРИГИНАЛЬНАЯ альфа
            resized = new_rgb.resize((w, h), Image.LANCZOS).convert("RGBA")
            resized.putalpha(orig.getchannel("A"))
            dds = encode_dds(resized, fourcc, n_mips, orig_bytes[:128])
            # 1) текстура по её родному пути
            files[target] = dds
            # 2) Трюк из моддерского FAQ HoMM5: часть .dds игра «в лоб» не
            #    подменяет. Поэтому кладём ту же текстуру под НОВЫМ именем и
            #    переписываем ссылающийся на неё .(Texture).xdb (DestName).
            folder, _, base = target.rpartition("/")
            stem = base[:-4] if base.lower().endswith(".dds") else base
            new_base = stem + ".h5mod.dds"
            new_path = (folder + "/" if folder else "") + new_base
            assert new_path not in pak.namelist(), f"имя занято: {new_path}"
            files[new_path] = dds
            xdb_path = target[:-4] + ".xdb"  # .dds -> .xdb, пара есть у всех
            xdb = pak.read(xdb_path).decode("utf-8")
            old_dest = f'<DestName href="{base}"/>'
            assert old_dest in xdb, f"DestName не найден в {xdb_path}"
            files[xdb_path] = xdb.replace(
                old_dest, f'<DestName href="{new_base}"/>').encode("utf-8")
            print(f"{png_name[:13]}… -> {w}x{h} {fourcc.decode()}  {target}")
    return files


def main():
    pak = open_data_pak()
    files = build(pak)
    for out in (OUT_H5U, OUT_PAK):
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
            for arcname, data in files.items():
                writestr_new(zout, arcname, data)
        print(f"\nГотово: {out}  ({len(files)} файлов, "
              f"{os.path.getsize(out) / 1e6:.1f} МБ)")


if __name__ == "__main__":
    main()
