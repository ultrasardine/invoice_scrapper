"""Flet desktop UI for Invoice Scrapper."""

import asyncio
from datetime import datetime
from pathlib import Path

import flet as ft

from invoice_scrapper.config import Config
from invoice_scrapper.excel_writer import write_excel
from invoice_scrapper.invoice_processor import InvoiceProcessor
from invoice_scrapper.models import InvoiceData


def main(page: ft.Page) -> None:
    page.title = "Invoice Scrapper"
    page.window.width = 900
    page.window.height = 750
    page.padding = 20

    # Load config
    config = Config.load()

    # --- State ---
    processing = False
    results_data: list[InvoiceData] = []

    # --- Controls ---
    input_dir_field = ft.TextField(
        label="Pasta de entrada",
        value=config.input_dir,
        expand=True,
        read_only=True,
    )
    output_file_field = ft.TextField(
        label="Ficheiro Excel de saída",
        value=config.output_file,
        expand=True,
        read_only=True,
    )
    progress_bar = ft.ProgressBar(visible=False)
    progress_text = ft.Text("")
    log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
    feedback_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
    process_btn = ft.ElevatedButton(
        "Processar Faturas",
        icon=ft.Icons.PLAY_ARROW,
    )

    # --- Field list ---
    field_controls: list[ft.Row] = []

    def _build_field_row(value: str) -> ft.Row:
        tf = ft.TextField(value=value, expand=True, dense=True)

        def remove_field(_):
            field_controls.remove(row)
            fields_column.controls.remove(row)
            page.update()

        remove_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            on_click=remove_field,
            tooltip="Remover campo",
        )
        row = ft.Row([tf, remove_btn], tight=True)
        return row

    for f in config.fields:
        row = _build_field_row(f)
        field_controls.append(row)

    fields_column = ft.Column(
        controls=list(field_controls),
        scroll=ft.ScrollMode.AUTO,
        height=200,
    )

    def _get_fields() -> list[str]:
        return [
            row.controls[0].value.strip()
            for row in field_controls
            if row.controls[0].value.strip()
        ]

    # --- Event handlers ---
    async def pick_input_dir(_):
        result = await ft.FilePicker().get_directory_path(
            dialog_title="Selecionar pasta de faturas",
            initial_directory=input_dir_field.value,
        )
        if result:
            input_dir_field.value = result
            page.update()

    async def pick_output_file(_):
        result = await ft.FilePicker().save_file(
            dialog_title="Selecionar ficheiro de saída",
            file_name=Path(output_file_field.value).name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
        )
        if result:
            output_file_field.value = result
            page.update()

    def add_field(_):
        row = _build_field_row("")
        field_controls.append(row)
        fields_column.controls.append(row)
        page.update()

    def save_config(_):
        cfg = Config(
            input_dir=input_dir_field.value,
            output_file=output_file_field.value,
            fields=_get_fields(),
        )
        cfg.save()
        _log("Configuração guardada")

    def load_config(_):
        nonlocal config
        config = Config.load()
        input_dir_field.value = config.input_dir
        output_file_field.value = config.output_file
        # Rebuild field list
        field_controls.clear()
        fields_column.controls.clear()
        for f in config.fields:
            row = _build_field_row(f)
            field_controls.append(row)
            fields_column.controls.append(row)
        _log("Configuração carregada")
        page.update()

    def _log(msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log_list.controls.append(ft.Text(f"[{ts}] {msg}", size=12))
        page.update()

    async def process_invoices(_):
        nonlocal processing, results_data
        if processing:
            return

        processing = True
        process_btn.disabled = True
        progress_bar.visible = True
        progress_bar.value = None  # Indeterminate
        feedback_text.value = "A processar..."
        results_data.clear()
        log_list.controls.clear()
        page.update()

        input_dir = Path(input_dir_field.value)
        output_file = Path(output_file_field.value)
        fields = _get_fields()

        if not input_dir.exists():
            _log(f"Erro: pasta '{input_dir}' não existe")
            processing = False
            process_btn.disabled = False
            progress_bar.visible = False
            feedback_text.value = "Erro: pasta de entrada não existe"
            page.update()
            return

        # Count PDFs for progress
        pdf_files = [
            f for f in input_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".pdf"
        ]
        total = len(pdf_files)

        if total == 0:
            _log("Nenhum ficheiro PDF encontrado")
            processing = False
            process_btn.disabled = False
            progress_bar.visible = False
            feedback_text.value = "Nenhum PDF encontrado"
            page.update()
            return

        _log(f"Encontrados {total} ficheiro(s) PDF")
        progress_bar.value = 0
        page.update()

        # Process in background
        def run_processing():
            processor = InvoiceProcessor(log_callback=_log)
            processed = 0
            successes = 0
            errors = 0
            total_items = 0

            for result in processor.process_directory(input_dir, fields):
                processed += 1
                if result.success and result.invoice:
                    results_data.append(result.invoice)
                    successes += 1
                    total_items += max(1, len(result.invoice.line_items))
                else:
                    errors += 1

                progress_bar.value = processed / total
                progress_text.value = f"{processed}/{total}"
                page.update()

            # Write Excel
            if results_data:
                _log(f"A escrever Excel: {output_file}")
                write_excel(results_data, output_file, fields)
                _log(f"✓ Ficheiro gerado: {output_file}")

            feedback_text.value = (
                f"Concluído: {successes} OK, {errors} erro(s), "
                f"{total_items} artigo(s)"
            )
            progress_bar.visible = False
            process_btn.disabled = False
            page.update()

        async def _run_in_thread():
            nonlocal processing
            await asyncio.to_thread(run_processing)
            processing = False

        page.run_task(_run_in_thread)

    process_btn.on_click = process_invoices

    # --- Layout ---
    page.add(
        ft.Column(
            [
                ft.Text("Invoice Scrapper", size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                # Input/Output paths
                ft.Row([
                    input_dir_field,
                    ft.ElevatedButton(
                        "Procurar",
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=pick_input_dir,
                    ),
                ]),
                ft.Row([
                    output_file_field,
                    ft.ElevatedButton(
                        "Procurar",
                        icon=ft.Icons.SAVE,
                        on_click=pick_output_file,
                    ),
                ]),
                ft.Divider(),
                # Fields section
                ft.Row([
                    ft.Text("Campos a extrair", size=16, weight=ft.FontWeight.W_500),
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                        on_click=add_field,
                        tooltip="Adicionar campo",
                    ),
                ]),
                fields_column,
                ft.Row([
                    ft.ElevatedButton(
                        "Guardar Config",
                        icon=ft.Icons.SAVE_ALT,
                        on_click=save_config,
                    ),
                    ft.ElevatedButton(
                        "Carregar Config",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=load_config,
                    ),
                ]),
                ft.Divider(),
                # Process button and progress
                ft.Row([process_btn, progress_text]),
                progress_bar,
                feedback_text,
                ft.Divider(),
                # Log area
                ft.Text("Log", size=16, weight=ft.FontWeight.W_500),
                ft.Container(
                    content=log_list,
                    height=200,
                    border=ft.border.all(1, ft.Colors.OUTLINE),
                    border_radius=8,
                    padding=8,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
    )
