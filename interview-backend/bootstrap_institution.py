"""Create the first institution and verified institution administrator.

Usage:
  python bootstrap_institution.py --name "Example University" \
      --slug example-university --admin-email admin@example.edu \
      --admin-name "Institution Admin"
"""
import argparse
import asyncio

from sqlalchemy import func, select

from database import AsyncSessionLocal
from models import Institution, InstitutionMembership, User


async def bootstrap(name: str, slug: str, email: str, admin_name: str | None) -> None:
    slug = slug.strip().lower()
    email = email.strip().lower()
    if not slug or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in slug):
        raise ValueError("slug may contain only lowercase letters, numbers, and hyphens")
    if "@" not in email:
        raise ValueError("admin email is invalid")

    async with AsyncSessionLocal() as db:
        institution = (await db.execute(select(Institution).where(Institution.slug == slug))).scalar_one_or_none()
        if institution is None:
            institution = Institution(name=name.strip(), slug=slug)
            db.add(institution)
            await db.flush()
        elif institution.name != name.strip():
            raise ValueError(f"slug {slug!r} already belongs to {institution.name!r}")

        user = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, name=admin_name, provider="institution_bootstrap")
            db.add(user)
            await db.flush()

        membership = (await db.execute(select(InstitutionMembership).where(
            InstitutionMembership.institution_id == institution.id,
            InstitutionMembership.user_id == user.id,
        ))).scalar_one_or_none()
        if membership is None:
            membership = InstitutionMembership(
                institution_id=institution.id,
                user_id=user.id,
                role="institution_admin",
                is_verified=True,
            )
            db.add(membership)
        else:
            membership.role = "institution_admin"
            membership.is_verified = True
        await db.commit()
        print(f"Institution ready: {institution.name} ({institution.id})")
        print(f"Administrator ready: {email} ({user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap an institution administrator")
    parser.add_argument("--name", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-name")
    args = parser.parse_args()
    asyncio.run(bootstrap(args.name, args.slug, args.admin_email, args.admin_name))


if __name__ == "__main__":
    main()
