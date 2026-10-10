import getpass

ENV_PATH = "/Users/siddarthbalagopal/patient-health-passport/backend/.env"

client_id = getpass.getpass("Paste new OPENEMR_CLIENT_ID, then press Enter: ")
client_secret = getpass.getpass("Paste new OPENEMR_CLIENT_SECRET, then press Enter: ")

with open(ENV_PATH) as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("OPENEMR_CLIENT_ID="):
        new_lines.append(f"OPENEMR_CLIENT_ID={client_id}\n")
    elif line.startswith("OPENEMR_CLIENT_SECRET="):
        new_lines.append(f"OPENEMR_CLIENT_SECRET={client_secret}\n")
    else:
        new_lines.append(line)

with open(ENV_PATH, "w") as f:
    f.writelines(new_lines)

print("Done. .env updated. Values were not echoed or logged anywhere.")
