import store


def print_tips(week: list[dict]) -> None:
    if len(week) < 3:
        print("\n💡 Tip: Aim for 3-5 quality applications per week.")


def generate_review(apps: list[dict], week: list[dict]) -> str:
    # hand-edited CSV rows can be short — treat missing fields as empty
    recent = sorted(apps, key=lambda x: x.get("status_date", ""), reverse=True)[:5]
    lines = []
    lines.append("\n=== WEEKLY JOB-SEARCH REVIEW ===")
    lines.append(f"Total applications logged: {len(apps)}")
    lines.append(f"Applications this week:   {len(week)}")
    lines.append("\nRecent applications (most recent first):")
    for app in recent:
        lines.append(
            f"  {app.get('status_date', '')}: {app['title']} @ {app['company']}"
            f" — {store.get_status(app)}"
        )
    return "\n".join(lines)


def main() -> None:
    apps = [j for j in store.load_jobs() if store.get_status(j) != "new"]

    if not apps:
        print("📂 No applications yet — mark a job applied on the dashboard first.")
        return

    week = store.this_week(apps, "status_date")
    print(generate_review(apps, week))
    print_tips(week)


if __name__ == "__main__":
    main()
