"""Quick test: fetch a LinkedIn profile and save the normalized JSON."""

import json
from linkedin_extractor import LinkedInClient

client = LinkedInClient()
result = client.get_profile("https://www.linkedin.com/in/adamselipsky/")

print(json.dumps(result, indent=2))

with open("test_output.json", "w") as f:
    json.dump(result, f, indent=2)

print("\nSaved to test_output.json")
