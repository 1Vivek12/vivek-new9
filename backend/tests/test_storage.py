"""Storage provider boundary and path traversal isolation tests."""

import io
import os
import tempfile

import pytest

from app.services.storage.local import LocalStorageProvider


@pytest.fixture
def temp_storage():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield LocalStorageProvider(base_dir=tmp_dir)


@pytest.mark.asyncio
async def test_tenant_storage_save_and_retrieve(temp_storage: LocalStorageProvider):
    """Verifies that files are correctly written to and retrieved from tenant directory."""
    tenant_id = "tenant-news9"
    relative_path = "media/report.txt"
    test_content = b"Gorakhpur news brief content"

    saved_path = await temp_storage.save_file(tenant_id, relative_path, io.BytesIO(test_content))
    assert os.path.exists(saved_path)
    assert tenant_id in saved_path

    retrieved = await temp_storage.get_file(tenant_id, relative_path)
    assert retrieved == test_content

    # Clean delete
    deleted = await temp_storage.delete_file(tenant_id, relative_path)
    assert deleted is True
    assert not await temp_storage.exists(tenant_id, relative_path)


@pytest.mark.asyncio
async def test_path_traversal_attack_is_strictly_blocked(temp_storage: LocalStorageProvider):
    """Verifies that directory traversal (../../) is caught and raises PermissionError."""
    tenant_id = "tenant-news9"
    traversal_path = "../../etc/passwd"

    with pytest.raises(PermissionError) as exc_info:
        await temp_storage.save_file(tenant_id, traversal_path, io.BytesIO(b"malicious payload"))
    assert "outside tenant boundary" in str(exc_info.value)


@pytest.mark.asyncio
async def test_storage_rejects_empty_tenant_id(temp_storage: LocalStorageProvider):
    """Verifies that storage operations without tenant ID are rejected immediately."""
    with pytest.raises(ValueError) as exc_info:
        await temp_storage.save_file("", "file.txt", io.BytesIO(b"content"))
    assert "Tenant ID is required" in str(exc_info.value)
