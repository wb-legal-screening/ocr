import logging
import os
from subprocess import run

import fitz
import pikepdf
from ocrmypdf.__main__ import run as run_ocrmypdf
from ocrmypdf._exec import tesseract

LEGAL_LANG = "ro_legal"
BACK_LANG = "ron"

LOGGER = logging.getLogger(__name__)


def get_language():
    tess_languages = tesseract.get_languages()
    return LEGAL_LANG if LEGAL_LANG in tess_languages else BACK_LANG


LANGUAGE = get_language()
LOGGER.info(f"Using language {LANGUAGE} for OCR")


WORD_LIST = "nlp/resources/custom-wordlist.txt"
USER_WORDS = []
if os.path.exists(WORD_LIST):
    USER_WORDS = ["--user-words", WORD_LIST]


CMD_ARGS = ["--skip-text", "-l", LANGUAGE] + USER_WORDS
# some PDF files might not be convertible to PDF/A
# then we try again with --output-type pdf
FAIL_SAFE_ARGS = ["--output-type", "pdf"]
OCRMYPDF = "ocrmypdf"


def is_pdf_encrypted(pdf_file_path: str) -> bool:
    with fitz.Document(pdf_file_path) as doc:
        if doc.needs_pass or doc.metadata is None or doc.is_encrypted:
            return True
        if doc.metadata is not None and doc.metadata.get("encryption", ""):
            return True
    return False


def remove_encryption(pdf_file_path: str):
    """Removes encryption by resaving the document

    Args:
        pdf_file_path (str): pdf file path
    """
    LOGGER.info(f"Saving unencrypted document: {pdf_file_path}")
    with pikepdf.open(pdf_file_path, allow_overwriting_input=True) as doc:
        doc.save(pdf_file_path)


def run_ocr(in_file, pdf_output):
    ocrmypdf_args = [*CMD_ARGS, in_file, pdf_output]
    exit_code = run_ocrmypdf(ocrmypdf_args)
    if exit_code != 0:
        LOGGER.info("OCR failed, trying again with --output-type pdf")
        ocrmypdf_args = [*FAIL_SAFE_ARGS, *CMD_ARGS, in_file, pdf_output]
        exit_code = run_ocrmypdf(ocrmypdf_args)
        if exit_code != 0:
            LOGGER.error("some error")


def call_ocr(in_file, pdf_output):
    ocrmypdf_args = [OCRMYPDF, "-v", *CMD_ARGS, in_file, pdf_output]
    proc = run(ocrmypdf_args, capture_output=True, encoding="utf-8")
    if proc.returncode != 0:
        LOGGER.info(
            "Input file could not be converted to PDF/A and OCR must be done again..."
        )
        ocrmypdf_args = [OCRMYPDF, *FAIL_SAFE_ARGS, *CMD_ARGS, in_file, pdf_output]
        proc = run(ocrmypdf_args, capture_output=True, encoding="utf-8")
        if proc.returncode != 0:
            LOGGER.error(proc.stderr)
            raise Exception(proc.stderr)
    LOGGER.debug(proc.stdout)
    LOGGER.debug(proc.stderr)
    return proc.stdout, proc.stderr


def get_ocrized_text(pdf_file):
    text = ""
    with fitz.open(pdf_file) as pdf_f:
        for page in pdf_f.pages():
            text += page.get_text()
    return text


def get_ocrized_text_from_blocks(pdf_file):
    text = ""
    with fitz.open(pdf_file) as pdf_f:
        for page in pdf_f.pages():
            blocks = page.get_text(option="blocks", flags=fitz.TEXTFLAGS_SEARCH)
            text += "\n".join([block[4].replace("\n", " ") for block in blocks]) + "\n"
    return text


def extract_ocrized_text(pdf_file, txt_output_file):
    text = get_ocrized_text(pdf_file)
    dump_text(text, txt_output_file)
    return text


def dump_text(text, txt_output_file):
    with open(txt_output_file, "w", encoding="utf-8") as txt_f:
        txt_f.write(text)
