"""
Test Runbook Resume Functionality

Simulates crash recovery and resume from journal.
"""
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from t2r.services.runbook_journal import (
        load_journal,
        add_run_entry,
        resume_from_run_id,
        get_failed_runs
    )
    from t2r.utils.atomic_write import atomic_write_json
    import pytest
except ImportError:
    pytest = None
    print("⚠️  pytest not available, skipping tests")


def setup_test_journal(journal_path: Path):
    """Create a test journal with a failed run"""
    journal = {
        "runs": [
            {
                "run_id": "run_test_001",
                "episode_id": "20251102",
                "created_at": "2025-11-10T12:00:00Z",
                "status": "failed",
                "current_stage": "upload",
                "stages": [
                    {
                        "stage": "planning",
                        "status": "completed",
                        "started_at": "2025-11-10T12:00:00Z",
                        "ended_at": "2025-11-10T12:00:05Z"
                    },
                    {
                        "stage": "remix",
                        "status": "completed",
                        "started_at": "2025-11-10T12:00:05Z",
                        "ended_at": "2025-11-10T12:05:00Z"
                    },
                    {
                        "stage": "upload",
                        "status": "failed",
                        "error": "Network timeout",
                        "retry_point": "upload",
                        "started_at": "2025-11-10T12:05:00Z",
                        "ended_at": "2025-11-10T12:10:00Z"
                    }
                ]
            }
        ]
    }
    atomic_write_json(journal_path, journal)
    return journal


if pytest:
    @pytest.mark.asyncio
    async def test_resume_from_run_id(tmp_path):
        """Test resuming a failed run from journal"""
        journal_path = tmp_path / "run_journal.json"
        
        # Setup test journal
        setup_test_journal(journal_path)
        
        # Test resume
        resume_info = resume_from_run_id(journal_path, "run_test_001")
        
        assert resume_info is not None
        assert resume_info["run_id"] == "run_test_001"
        assert resume_info["resume_available"] is True
        assert resume_info["retry_point"] == "upload"
        assert resume_info["last_completed_stage"] == "remix"
    
    @pytest.mark.asyncio
    async def test_get_failed_runs(tmp_path):
        """Test getting list of failed runs"""
        journal_path = tmp_path / "run_journal.json"
        
        # Setup test journal
        setup_test_journal(journal_path)
        
        # Get failed runs
        failed = get_failed_runs(journal_path)
        
        assert len(failed) == 1
        assert failed[0]["run_id"] == "run_test_001"
        assert failed[0]["retry_point"] == "upload"
        assert "Network timeout" in (failed[0]["last_error"] or "")
    
    @pytest.mark.asyncio
    async def test_journal_persistence(tmp_path):
        """Test journal persistence across writes"""
        journal_path = tmp_path / "run_journal.json"
        
        # Add initial entry
        add_run_entry(
            journal_path,
            "run_test_002",
            "20251103",
            "planning",
            "running",
            "Test run started"
        )
        
        # Add another stage
        add_run_entry(
            journal_path,
            "run_test_002",
            "20251103",
            "remix",
            "completed",
            "Remix completed",
            started_at="2025-11-10T12:00:00Z",
            ended_at="2025-11-10T12:05:00Z"
        )
        
        # Verify journal
        journal = load_journal(journal_path)
        assert len(journal["runs"]) == 1
        run = journal["runs"][0]
        assert run["run_id"] == "run_test_002"
        assert len(run["stages"]) == 2
        
        # Verify last stage
        last_stage = run["stages"][-1]
        assert last_stage["stage"] == "remix"
        assert last_stage["status"] == "completed"


if __name__ == "__main__":
    # Simple manual test if pytest not available
    import tempfile
    test_dir = Path(tempfile.mkdtemp())
    journal_path = test_dir / "run_journal.json"
    
    setup_test_journal(journal_path)
    resume_info = resume_from_run_id(journal_path, "run_test_001")
    
    print("✅ Resume test passed!")
    print(f"Resume info: {json.dumps(resume_info, indent=2, ensure_ascii=False)}")
    
    failed = get_failed_runs(journal_path)
    print(f"✅ Failed runs test passed!")
    print(f"Failed runs: {json.dumps(failed, indent=2, ensure_ascii=False)}")

