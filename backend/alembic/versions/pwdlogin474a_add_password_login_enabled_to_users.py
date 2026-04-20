"""add password_login_enabled to users

Revision ID: pwdlogin474a
Revises: oauth470aiqi
Create Date: 2026-04-20 20:35:00.000000

Rationale (TASK-474):
Adds an explicit boolean on the users row indicating whether the account
has a real, user-chosen password. OAuth-only accounts (created via
provider sign-in without ever setting a password) are False; everyone
else is True. This lets operator queries answer "which accounts are
OAuth-only?" without joining oauth_identities.

Backfill heuristic: a user whose first oauth_identity row was created
within 10 seconds of the user row itself was almost certainly created
via the OAuth-only path in ``auth._resolve_oauth_user`` (which inserts
both rows in the same flush). Users with a wider gap had OAuth linked
after the fact, which means they had a real password first — they stay
True. The heuristic is best-effort; operators who care about perfect
historical accuracy can reconcile from oauth_identities. A misclassified
row has no user-facing impact because the login path does not gate on
this flag — it exists purely for operator visibility.

PostgreSQL-only: the UPDATE uses INTERVAL literal syntax. Production is
Postgres; the test suite bootstraps via ``Base.metadata.create_all`` and
skips alembic. Local SQLite runs of ``alembic upgrade head`` will fail
on the INTERVAL expression.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "pwdlogin474a"
down_revision: Union[str, None] = "oauth470aiqi"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "password_login_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        """
        UPDATE users
        SET password_login_enabled = false
        WHERE EXISTS (
            SELECT 1 FROM oauth_identities oi
            WHERE oi.user_id = users.id
              AND oi.created_at - users.created_at < INTERVAL '10 seconds'
        )
        """
    )


def downgrade() -> None:
    op.drop_column("users", "password_login_enabled")
