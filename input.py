import shelve

with shelve.open("rewards_db") as rewards:
    for key, value in rewards.items():
        print(f"{key}: {value} (type: {type(value)})")