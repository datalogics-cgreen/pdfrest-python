from __future__ import annotations

from collections.abc import Sequence

import pytest

from pdfrest import AsyncPdfRestClient, PdfRestApiError, PdfRestClient
from pdfrest.models import PdfRestFile
from pdfrest.types import PdfMergeInput, PdfPageSelection

from ..resources import get_test_resource_path


def _expand_page_selection(
    selection: PdfPageSelection | Sequence[PdfPageSelection],
    *,
    total_pages: int,
) -> list[int]:
    def expand_entry(entry: PdfPageSelection) -> list[int]:
        if isinstance(entry, int):
            return [entry]
        text = str(entry).strip()
        lowered = text.lower()
        if lowered == "even":
            return list(range(2, total_pages + 1, 2))
        if lowered == "odd":
            return list(range(1, total_pages + 1, 2))
        if lowered == "last":
            return [total_pages]
        if "-" in lowered:
            start_raw, end_raw = (part.strip() for part in lowered.split("-", 1))

            def resolve(range_token: str) -> int:
                return total_pages if range_token == "last" else int(range_token)  # noqa: S105

            start = resolve(start_raw)
            end = resolve(end_raw)
            step = 1 if end >= start else -1
            return list(range(start, end + step, step))
        return [int(text)]

    if isinstance(selection, Sequence) and not isinstance(
        selection, (str, bytes, bytearray)
    ):
        expanded: list[int] = []
        for segment in selection:
            expanded.extend(expand_entry(segment))
        return expanded
    return expand_entry(selection)


def _extract_merge_entry(
    entry: PdfMergeInput,
) -> tuple[PdfRestFile, PdfPageSelection | Sequence[PdfPageSelection]]:
    if isinstance(entry, tuple):
        return entry
    if isinstance(entry, dict):
        file = entry["file"]
        pages = entry.get("pages")
        selection: PdfPageSelection | Sequence[PdfPageSelection] = (
            pages if pages is not None else "1-last"
        )
        return file, selection
    return entry, "1-last"


def _fetch_page_count(client: PdfRestClient, file: PdfRestFile) -> int:
    info = client.query_pdf_info(file)
    assert info.page_count is not None
    return int(info.page_count)


async def _fetch_page_count_async(client: AsyncPdfRestClient, file: PdfRestFile) -> int:
    info = await client.query_pdf_info(file)
    assert info.page_count is not None
    return int(info.page_count)


@pytest.fixture(scope="module")
def uploaded_live_pdfs(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
) -> tuple[PdfRestFile, PdfRestFile]:
    split_source_path = get_test_resource_path("20-pages.pdf")
    merge_partner_path = get_test_resource_path("report.pdf")

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        split_source = client.files.create_from_paths([split_source_path])[0]
        merge_partner = client.files.create_from_paths([merge_partner_path])[0]

    return split_source, merge_partner


@pytest.mark.parametrize(
    ("page_groups", "expected_count"),
    [
        pytest.param(["1-5", "6-last"], 2, id="two-ranges"),
        pytest.param([["1", "3", "5"], "2-4"], 2, id="alternating-selection"),
        pytest.param(["even"], 1, id="even-only"),
        pytest.param(["9-2"], 1, id="descending-single"),
        pytest.param(["odd", "even"], 2, id="odd-and-even"),
    ],
)
def test_live_split_pdf_page_groups(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
    page_groups: list[PdfPageSelection],
    expected_count: int,
) -> None:
    split_source, _ = uploaded_live_pdfs

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        total_pages = _fetch_page_count(client, split_source)

        response = client.split_pdf(
            split_source,
            page_groups=page_groups,
            output_prefix="live-split",
        )

        assert len(response.output_files) == expected_count

        output_infos = [
            client.query_pdf_info(output_file) for output_file in response.output_files
        ]

        assert all(
            output_file.name.startswith("live-split")
            and output_file.name.endswith(".pdf")
            and output_file.type == "application/pdf"
            and output_file.size > 0
            for output_file in response.output_files
        )
        page_counts_optional = [info.page_count for info in output_infos]
        assert all(count is not None for count in page_counts_optional)
        expected_page_counts = [
            len(_expand_page_selection(group, total_pages=total_pages))
            for group in page_groups
        ][: len(page_counts_optional)]
        page_counts = [
            int(count) for count in page_counts_optional if count is not None
        ]
        assert page_counts == expected_page_counts
        assert str(response.input_id) == str(split_source.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page_groups", "expected_count"),
    [
        pytest.param(["1-5", "6-last"], 2, id="two-ranges"),
        pytest.param([["1", "3", "5"], "2-4"], 2, id="alternating-selection"),
        pytest.param(["even"], 1, id="even-only"),
        pytest.param(["9-2"], 1, id="descending-single"),
        pytest.param(["odd", "even"], 2, id="odd-and-even"),
    ],
)
async def test_live_async_split_pdf_page_groups(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
    page_groups: list[PdfPageSelection],
    expected_count: int,
) -> None:
    split_source, _ = uploaded_live_pdfs

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        total_pages = await _fetch_page_count_async(client, split_source)

        response = await client.split_pdf(
            split_source,
            page_groups=page_groups,
            output_prefix="live-async-split",
        )

        assert len(response.output_files) == expected_count

        output_infos = [
            await client.query_pdf_info(output_file)
            for output_file in response.output_files
        ]

        assert all(
            output_file.name.startswith("live-async-split")
            and output_file.name.endswith(".pdf")
            and output_file.type == "application/pdf"
            and output_file.size > 0
            for output_file in response.output_files
        )
        page_counts_optional = [info.page_count for info in output_infos]
        assert all(count is not None for count in page_counts_optional)
        expected_page_counts = [
            len(_expand_page_selection(group, total_pages=total_pages))
            for group in page_groups
        ][: len(page_counts_optional)]
        page_counts = [
            int(count) for count in page_counts_optional if count is not None
        ]
        assert page_counts == expected_page_counts
        assert str(response.input_id) == str(split_source.id)


def test_live_split_pdf_default_outputs(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, _ = uploaded_live_pdfs

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        total_pages = _fetch_page_count(client, split_source)

        response = client.split_pdf(
            split_source,
            output_prefix="live-split-default",
        )

        assert len(response.output_files) == total_pages

        output_infos = [
            client.query_pdf_info(output_file) for output_file in response.output_files
        ]
        assert all(
            output_file.name.startswith("live-split-default")
            and output_file.name.endswith(".pdf")
            and output_file.type == "application/pdf"
            and output_file.size > 0
            for output_file in response.output_files
        )
        assert all(info.page_count == 1 for info in output_infos)

        assert str(response.input_id) == str(split_source.id)


@pytest.mark.asyncio
async def test_live_async_split_pdf_default_outputs(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, _ = uploaded_live_pdfs

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        total_pages = await _fetch_page_count_async(client, split_source)

        response = await client.split_pdf(
            split_source,
            output_prefix="live-async-split-default",
        )

        assert len(response.output_files) == total_pages

        output_infos = [
            await client.query_pdf_info(output_file)
            for output_file in response.output_files
        ]
        assert all(
            output_file.name.startswith("live-async-split-default")
            and output_file.name.endswith(".pdf")
            and output_file.type == "application/pdf"
            and output_file.size > 0
            for output_file in response.output_files
        )
        assert all(info.page_count == 1 for info in output_infos)

        assert str(response.input_id) == str(split_source.id)


def test_live_split_pdf_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, _ = uploaded_live_pdfs

    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)page"),
    ):
        client.split_pdf(
            split_source,
            page_groups=["1-2"],
            extra_body={"pages": ["0"]},
        )


@pytest.mark.asyncio
async def test_live_async_split_pdf_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, _ = uploaded_live_pdfs

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            await client.split_pdf(
                split_source,
                page_groups=["1-2"],
                extra_body={"pages": ["0"]},
            )


def test_live_merge_pdfs_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, merge_partner = uploaded_live_pdfs
    sources: list[PdfMergeInput] = [
        {"file": split_source, "pages": "odd"},
        {"file": split_source, "pages": "even"},
        {"file": merge_partner, "pages": "1"},
    ]

    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        source_infos = {
            str(candidate.id): _fetch_page_count(client, candidate)
            for candidate in (split_source, merge_partner)
        }

        response = client.merge_pdfs(
            sources,
            output_prefix="live-merge",
        )

        assert len(response.input_ids) == len(sources)

        expected_total_pages = sum(
            len(
                _expand_page_selection(
                    selection, total_pages=source_infos[str(file.id)]
                )
            )
            for file, selection in (_extract_merge_entry(entry) for entry in sources)
        )

        output_file = response.output_file
        assert output_file.name.startswith("live-merge")
        assert output_file.name.endswith(".pdf")
        assert output_file.type == "application/pdf"
        assert output_file.size > 0

        output_info = client.query_pdf_info(output_file)
        assert output_info.page_count == expected_total_pages


@pytest.mark.asyncio
async def test_live_async_merge_pdfs_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, merge_partner = uploaded_live_pdfs
    sources: list[PdfMergeInput] = [
        {"file": split_source, "pages": "even"},
        {"file": merge_partner, "pages": "1"},
    ]

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        with pytest.raises(PdfRestApiError, match=r"(?i)page"):
            await client.merge_pdfs(
                sources,
                output_prefix="live-async-merge-invalid",
                extra_body={"pages": ["even", "0"]},
            )


def test_live_merge_pdfs_invalid_pages(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, merge_partner = uploaded_live_pdfs
    sources: list[PdfMergeInput] = [
        {"file": split_source, "pages": "even"},
        {"file": merge_partner, "pages": "1"},
    ]

    with (
        PdfRestClient(
            api_key=pdfrest_api_key,
            base_url=pdfrest_live_base_url,
        ) as client,
        pytest.raises(PdfRestApiError, match=r"(?i)page"),
    ):
        client.merge_pdfs(
            sources,
            output_prefix="live-merge-invalid",
            extra_body={"pages": ["even", "0"]},
        )


@pytest.mark.asyncio
async def test_live_async_merge_pdfs_success(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
) -> None:
    split_source, merge_partner = uploaded_live_pdfs
    sources: list[PdfMergeInput] = [
        {"file": split_source, "pages": "9-2"},
        {"file": merge_partner, "pages": "1"},
    ]

    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        split_page_count = await _fetch_page_count_async(client, split_source)
        partner_page_count = await _fetch_page_count_async(client, merge_partner)

        response = await client.merge_pdfs(
            sources,
            output_prefix="live-async-merge",
        )

        source_page_counts = {
            str(split_source.id): split_page_count,
            str(merge_partner.id): partner_page_count,
        }
        expected_total_pages = sum(
            len(
                _expand_page_selection(
                    selection, total_pages=source_page_counts[str(file.id)]
                )
            )
            for file, selection in (_extract_merge_entry(entry) for entry in sources)
        )

        output_file = response.output_file
        assert output_file.name.startswith("live-async-merge")
        assert output_file.name.endswith(".pdf")
        assert output_file.type == "application/pdf"
        assert output_file.size > 0

        output_info = await client.query_pdf_info(output_file)
        assert output_info.page_count == expected_total_pages


SPLIT_RANGE_CASES = [
    pytest.param("3", True, False, id="single-str"),
    pytest.param(3, True, False, id="single-int"),
    pytest.param("2-5", True, False, id="ascending-range"),
    pytest.param("5-2", True, False, id="descending-range"),
    pytest.param("even", True, False, id="even"),
    pytest.param("odd", True, False, id="odd"),
    pytest.param("2-last", True, False, id="to-last"),
    pytest.param("last-2", True, False, id="last-desc"),
    pytest.param("last", False, True, id="last"),
]


@pytest.mark.parametrize(
    ("selection", "expect_success", "requires_override"), SPLIT_RANGE_CASES
)
def test_live_split_pdf_page_range_variants(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
    selection: PdfPageSelection,
    expect_success: bool,
    requires_override: bool,
    request: pytest.FixtureRequest,
) -> None:
    split_source, _ = uploaded_live_pdfs
    case_id = request.node.callspec.id
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        total_pages = _fetch_page_count(client, split_source)
        override_body = None
        if requires_override:
            override_body = {"pages": [str(selection)]}

        if expect_success:
            response = client.split_pdf(
                split_source,
                page_groups=[selection if not requires_override else "1"],
                output_prefix=f"live-split-range-{case_id}",
                extra_body=override_body,
            )
            expected_pages = _expand_page_selection(selection, total_pages=total_pages)
            output_pages = client.query_pdf_info(response.output_files[0]).page_count
            assert output_pages == len(expected_pages)
        else:
            with pytest.raises(PdfRestApiError, match=r"(?i)page"):
                client.split_pdf(
                    split_source,
                    page_groups=[selection if not requires_override else "1"],
                    output_prefix=f"live-split-range-{case_id}",
                    extra_body=override_body,
                )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selection", "expect_success", "requires_override"), SPLIT_RANGE_CASES
)
async def test_live_async_split_pdf_page_range_variants(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
    selection: PdfPageSelection,
    expect_success: bool,
    requires_override: bool,
    request: pytest.FixtureRequest,
) -> None:
    split_source, _ = uploaded_live_pdfs
    case_id = request.node.callspec.id
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        total_pages = await _fetch_page_count_async(client, split_source)
        override_body = None
        if requires_override:
            override_body = {"pages": [str(selection)]}

        if expect_success:
            response = await client.split_pdf(
                split_source,
                page_groups=[selection if not requires_override else "1"],
                output_prefix=f"live-async-split-range-{case_id}",
                extra_body=override_body,
            )
            expected_pages = _expand_page_selection(selection, total_pages=total_pages)
            output_pages = (
                await client.query_pdf_info(response.output_files[0])
            ).page_count
            assert output_pages == len(expected_pages)
        else:
            with pytest.raises(PdfRestApiError, match=r"(?i)page"):
                await client.split_pdf(
                    split_source,
                    page_groups=[selection if not requires_override else "1"],
                    output_prefix=f"live-async-split-range-{case_id}",
                    extra_body=override_body,
                )


MERGE_RANGE_CASES = [
    pytest.param("3", True, False, id="single-str"),
    pytest.param(3, True, False, id="single-int"),
    pytest.param("2-5", True, False, id="ascending-range"),
    pytest.param("5-2", True, False, id="descending-range"),
    pytest.param("even", True, False, id="even"),
    pytest.param("odd", True, False, id="odd"),
    pytest.param("2-last", True, False, id="to-last"),
    pytest.param("last-2", True, False, id="last-desc"),
    pytest.param("last", False, False, id="last"),
]


@pytest.mark.parametrize(
    ("selection", "expect_success", "requires_override"), MERGE_RANGE_CASES
)
def test_live_merge_pdf_page_range_variants(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
    selection: PdfPageSelection,
    expect_success: bool,
    requires_override: bool,
    request: pytest.FixtureRequest,
) -> None:
    split_source, merge_partner = uploaded_live_pdfs
    case_id = request.node.callspec.id
    with PdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        source_page_counts = {
            str(split_source.id): _fetch_page_count(client, split_source),
            str(merge_partner.id): _fetch_page_count(client, merge_partner),
        }
        sources: list[PdfMergeInput] = [
            {
                "file": split_source,
                "pages": selection if not requires_override else "1",
            },
            {"file": merge_partner, "pages": "1"},
        ]
        override_body = {"pages": [str(selection), "1"]} if requires_override else None

        if expect_success:
            response = client.merge_pdfs(
                sources,
                output_prefix=f"live-merge-range-{case_id}",
                extra_body=override_body,
            )
            expected_total_pages = sum(
                len(
                    _expand_page_selection(
                        chosen_selection,
                        total_pages=source_page_counts[str(file.id)],
                    )
                )
                for file, chosen_selection in (
                    _extract_merge_entry(entry) for entry in sources
                )
            )
            output_info = client.query_pdf_info(response.output_file)
            assert output_info.page_count == expected_total_pages
        else:
            with pytest.raises(PdfRestApiError, match=r"(?i)page"):
                client.merge_pdfs(
                    sources,
                    output_prefix=f"live-merge-range-{case_id}",
                    extra_body=override_body,
                )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selection", "expect_success", "requires_override"), MERGE_RANGE_CASES
)
async def test_live_async_merge_pdf_page_range_variants(
    pdfrest_api_key: str,
    pdfrest_live_base_url: str,
    uploaded_live_pdfs: tuple[PdfRestFile, PdfRestFile],
    selection: PdfPageSelection,
    expect_success: bool,
    requires_override: bool,
    request: pytest.FixtureRequest,
) -> None:
    split_source, merge_partner = uploaded_live_pdfs
    case_id = request.node.callspec.id
    async with AsyncPdfRestClient(
        api_key=pdfrest_api_key,
        base_url=pdfrest_live_base_url,
    ) as client:
        source_page_counts = {
            str(split_source.id): await _fetch_page_count_async(client, split_source),
            str(merge_partner.id): await _fetch_page_count_async(client, merge_partner),
        }
        sources: list[PdfMergeInput] = [
            {
                "file": split_source,
                "pages": selection if not requires_override else "1",
            },
            {"file": merge_partner, "pages": "1"},
        ]
        override_body = {"pages": [str(selection), "1"]} if requires_override else None

        if expect_success:
            response = await client.merge_pdfs(
                sources,
                output_prefix=f"live-async-merge-range-{case_id}",
                extra_body=override_body,
            )
            expected_total_pages = sum(
                len(
                    _expand_page_selection(
                        chosen_selection,
                        total_pages=source_page_counts[str(file.id)],
                    )
                )
                for file, chosen_selection in (
                    _extract_merge_entry(entry) for entry in sources
                )
            )
            output_info = await client.query_pdf_info(response.output_file)
            assert output_info.page_count == expected_total_pages
        else:
            with pytest.raises(PdfRestApiError, match=r"(?i)page"):
                await client.merge_pdfs(
                    sources,
                    output_prefix=f"live-async-merge-range-{case_id}",
                    extra_body=override_body,
                )
