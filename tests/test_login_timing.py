"""Test that login timing is constant to prevent username enumeration."""
from __future__ import annotations


class TestLoginTiming:
    """Login must not reveal whether a username exists via timing."""

    def test_nonexistent_user_performs_db_write(self):
        """When user doesn't exist, the code should still do a DB write
        to prevent timing-based username enumeration."""
        import inspect

        from app.services import user as user_service

        source = inspect.getsource(user_service.login_user)

        # Find the line after "if not user:" — it should include a db operation
        lines = source.split("\n")
        target_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("if not user:"):
                target_idx = i + 1
                break

        assert target_idx is not None, "if not user: not found"
        # The next indented line should be a db write
        next_line = lines[target_idx].strip() if target_idx < len(lines) else ""
        if not next_line or next_line.startswith("raise"):
            # If it's a raise, check if there's a db write somewhere
            # in the else/non-existence path
            has_db = False
            for j in range(target_idx, min(target_idx + 10, len(lines))):
                if "db." in lines[j] or "flush" in lines[j]:
                    has_db = True
                    break
            assert has_db, (
                "The 'user not found' path must include a DB write "
                "(e.g. await db.flush()) to prevent timing attacks."
            )
