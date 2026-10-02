"""Deterministic local checks: Google calls and peak inline-buffer allocations. No network."""

from __future__ import annotations

import json
import tracemalloc
from unittest.mock import Mock

from app.errors import DriveContentTooLargeError
from app.google.drive_client import LimitedDownloadBuffer
from app.schemas.drive import DriveSearchFilesAdvancedInput
from app.services.drive_service import DriveService


def main():
    service = DriveService(Mock())
    service.client = Mock()
    service.client.list_files.return_value = {"files": []}
    service.search_files_advanced(
        external_subject="check",
        input_data=DriveSearchFilesAdvancedInput(
            terms=["one", "two", "three", "four", "five"],
            mime_types=["text/plain"],
        ),
    )
    assert service.client.list_files.call_count == 1
    limit = 262144
    chunk = b"x" * 65536
    tracemalloc.start()
    buffer = LimitedDownloadBuffer(limit)
    try:
        for _ in range(64):  # A simulated 4 MiB file must stop after four chunks.
            buffer.write(chunk)
    except DriveContentTooLargeError:
        pass
    else:
        raise AssertionError("Oversized content was accepted")
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert buffer.tell() == limit
    print(
        json.dumps(
            {
                "all_terms_calls_before": 6,
                "all_terms_calls_now": service.client.list_files.call_count,
                "simulated_file_bytes": 4194304,
                "buffer_bytes": buffer.tell(),
                "peak_buffer_allocation_bytes": peak,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
