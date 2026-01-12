from datetime import datetime, timezone

# Test with the created timestamp from the batch
test_dates = [
    '2026-01-13T01:15:14Z',
    '2026-01-13T01:15:14.000Z', 
    '2026-01-13T01:15:14',
    '1/13/2026, 1:15:14 am'  # Frontend display format
]

now = datetime.now(timezone.utc)
print(f"Current UTC time: {now}")
print(f"Current local time: {datetime.now()}")
print()

for date_str in test_dates:
    try:
        if date_str.endswith("Z"):
            created = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            created = datetime.fromisoformat(date_str)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
        
        age_seconds = (now - created).total_seconds()
        age_hours = age_seconds / 3600
        age_days = age_seconds / 86400
        
        print(f"Date: {date_str}")
        print(f"  Parsed: {created}")
        print(f"  Age: {age_days:.2f} days / {age_hours:.2f} hours")
        print()
    except Exception as e:
        print(f"Date: {date_str}")
        print(f"  ERROR: {e}")
        print()
