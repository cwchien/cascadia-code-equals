import multiprocessing
import os
import shutil
import subprocess
import sys
from pathlib import Path

import fontTools.designspaceLib
import ufo2ft
import ufoLib2
from ufo2ft.instantiator import Instantiator

VERSION_YEAR_MONTH = 2407
VERSION_DAY = 24
OUTPUT_DIR = Path("build")
OUTPUT_TTF_DIR = OUTPUT_DIR / "ttf"
OUTPUT_UNHINTED_DIR = OUTPUT_TTF_DIR / "unhinted"
OUTPUT_HINTED_DIR = OUTPUT_TTF_DIR / "hinted"
INPUT_DIR = Path("sources")
FEATURES_DIR = INPUT_DIR / "features"

FAMILY_NAME = "Cascadia Code"
# Only these static instances are built.
STYLES = {"Regular", "Bold", "Italic", "Bold Italic"}

# Font modifications
# ****************************************************************


def step_set_feature_file(path: Path, name: str, instance: ufoLib2.Font) -> None:
    featureSet = ""
    if "Italic" in name: #until I can come up with a more elegent solution, this'll do.
        featureList = [
            "header_italic", # adds definitions, language systems
            "aalt_italic",
            "ccmp",
            "locl_italic",
            "calt_italic",
            "figures_italic", # contains subs/sinf/sups/numr/dnom
            "frac",
            "ordn",
            "case",
            "salt",
            "ss01",
            "ss02",
            "ss03",
            "ss19",
            "ss20",
            "rclt",
            "zero"
            ]
    else:
        featureList = [
            "header", # adds definitions, language systems
            "aalt",
            "ccmp",
            "locl",
            "calt",
            "figures", # contains subs/sinf/sups/numr/dnom
            "frac",
            "ordn",
            "case",
            "ss02",
            "ss19",
            "ss20",
            "rclt",
            "zero",
            "init",
            "medi",
            "fina",
            "rlig",
            ]

    for item in featureList:
        featureSet += Path(path / str(item+".fea")).read_text()
    instance.features.text = featureSet


def set_font_metaData(font: ufoLib2.Font) -> None:
    font.info.versionMajor = VERSION_YEAR_MONTH
    font.info.versionMinor = VERSION_DAY

    font.info.openTypeOS2TypoAscender = 1900
    font.info.openTypeOS2TypoDescender = -480
    font.info.openTypeOS2TypoLineGap = 0

    font.info.openTypeHheaAscender = font.info.openTypeOS2TypoAscender
    font.info.openTypeHheaDescender = font.info.openTypeOS2TypoDescender
    font.info.openTypeHheaLineGap = font.info.openTypeOS2TypoLineGap

    font.info.openTypeOS2WinAscent = 2226
    font.info.openTypeOS2WinDescent = abs(font.info.openTypeOS2TypoDescender)

    font.info.openTypeGaspRangeRecords = [
        {"rangeMaxPPEM": 9, "rangeGaspBehavior": [1, 3]},
        {"rangeMaxPPEM": 50, "rangeGaspBehavior": [0, 1, 2, 3]},
        {"rangeMaxPPEM": 65535, "rangeGaspBehavior": [1, 3]},
    ]


def prepare_fonts(
    designspace: fontTools.designspaceLib.DesignSpaceDocument, name: str
) -> None:
    designspace.loadSourceFonts(ufoLib2.Font.open)
    for source in designspace.sources:
        step_set_feature_file(FEATURES_DIR, name, source.font)
        set_font_metaData(source.font)


# Build fonts
# ****************************************************************


def build_font_static(
    designspace: fontTools.designspaceLib.DesignSpaceDocument,
    instance_descriptor: fontTools.designspaceLib.InstanceDescriptor,
    name: str,
) -> None:
    prepare_fonts(designspace, name)

    generator = Instantiator.from_designspace(designspace)
    instance = generator.generate_instance(instance_descriptor)
    instance.info.familyName = instance.info.familyName.replace(" Italic","")
    if instance.info.styleMapFamilyName:
        instance.info.styleMapFamilyName = instance.info.styleMapFamilyName.replace(" Italic","")
    compile_static_and_save(instance, name.replace(" Italic",""))


# Export fonts
# ****************************************************************


def compile_static_and_save(instance: ufoLib2.Font, name: str) -> None:
    family_name = name
    style_name = instance.info.styleName
    print(f"[{family_name}] Building static instance: {style_name}")

    # Use pathops backend for overlap removal because it is, at the time of this
    # writing, massively faster than booleanOperations and thanks to autohinting,
    # there is no need to keep outlines compatible to previous releases.
    static_ttf = ufo2ft.compileTTF(
        instance, removeOverlaps=True, overlapsBackend="pathops"
    )

    file_name = f"{family_name}-{style_name}".replace(" ", "")
    file_path = (OUTPUT_UNHINTED_DIR / file_name).with_suffix(".ttf")
    file_path.parent.mkdir(exist_ok=True, parents=True)
    static_ttf.save(file_path)
    print(f"[{family_name}] Done: {file_path}")


# Font hinting
# ****************************************************************


def ttfautohint(source: Path, target: Path) -> None:
    print(f"Autohinting {source} -> {target}")
    target.parent.mkdir(exist_ok=True, parents=True)
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "ttfautohint",
            "--stem-width",
            "nsn",
            "--increase-x-height",
            "0",
            "--reference",
            os.fspath(OUTPUT_UNHINTED_DIR / "CascadiaCode-Regular.ttf"),
            os.fspath(source),
            os.fspath(target),
        ]
    )


# Main build script
# ****************************************************************


def load_designspace(file_name: str) -> fontTools.designspaceLib.DesignSpaceDocument:
    # Load Designspace and keep only the instances we want to build.
    designspace = fontTools.designspaceLib.DesignSpaceDocument.fromfile(
        INPUT_DIR / file_name
    )
    designspace.instances = [
        s
        for s in designspace.instances
        if s.lib.get("com.schriftgestaltung.export", True)
        and s.styleName in STYLES
    ]
    return designspace


if __name__ == "__main__":
    shutil.rmtree(OUTPUT_TTF_DIR, ignore_errors=True)

    designspace = load_designspace("CascadiaCode_variable.designspace")
    designspaceItalic = load_designspace("CascadiaCode_variable_italic.designspace")

    # Stage 1: Build the unhinted static TTFs.
    jobs = [
        (designspace, instance_descriptor, FAMILY_NAME)
        for instance_descriptor in designspace.instances
    ] + [
        (designspaceItalic, instance_descriptor, f"{FAMILY_NAME} Italic")
        for instance_descriptor in designspaceItalic.instances
    ]
    with multiprocessing.Pool(processes=min(len(jobs), multiprocessing.cpu_count())) as pool:
        processes = [pool.apply_async(build_font_static, job) for job in jobs]
        for process in processes:
            process.get()

    # Stage 2: Autohint into a separate folder, keeping the unhinted copies.
    for ttf_path in sorted(OUTPUT_UNHINTED_DIR.glob("*.ttf")):
        ttfautohint(ttf_path, OUTPUT_HINTED_DIR / ttf_path.name)

    print("All done.")
