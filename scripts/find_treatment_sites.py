"""Find sites that would be assigned to treatment arm."""

import hashlib
import sys

sys.path.insert(0, "c:/Users/joeba/Documents/findable")

from uuid import NAMESPACE_DNS, uuid5


def get_arm(domain: str, treatment_allocation: float = 0.5) -> str:
    """Simulate experiment arm assignment for a domain."""
    # Create a deterministic UUID from domain (like site_id would be)
    site_id = uuid5(NAMESPACE_DNS, domain)

    # Same logic as get_experiment_arm()
    hash_input = str(site_id).encode("utf-8")
    hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16)
    normalized = (hash_value % 10000) / 10000.0

    if normalized < treatment_allocation:
        return "TREATMENT"
    return "CONTROL"


# Test a bunch of popular/diverse domains
domains = [
    # Tech
    "microsoft.com",
    "apple.com",
    "google.com",
    "amazon.com",
    "meta.com",
    "nvidia.com",
    "intel.com",
    "amd.com",
    "ibm.com",
    "oracle.com",
    # Dev tools
    "github.com",
    "gitlab.com",
    "bitbucket.org",
    "stackoverflow.com",
    "npmjs.com",
    "pypi.org",
    "crates.io",
    "docker.com",
    "kubernetes.io",
    # AI
    "openai.com",
    "anthropic.com",
    "deepmind.com",
    "huggingface.co",
    "cohere.com",
    # Cloud
    "aws.amazon.com",
    "cloud.google.com",
    "azure.microsoft.com",
    "digitalocean.com",
    "heroku.com",
    "railway.app",
    "vercel.com",
    "netlify.com",
    # Docs/Learning
    "docs.python.org",
    "developer.mozilla.org",
    "reactjs.org",
    "vuejs.org",
    "angular.io",
    "svelte.dev",
    "nextjs.org",
    "fastapi.tiangolo.com",
    # SaaS
    "notion.so",
    "slack.com",
    "zoom.us",
    "figma.com",
    "canva.com",
    "airtable.com",
    "asana.com",
    "monday.com",
    "linear.app",
    "jira.atlassian.com",
    # Finance
    "stripe.com",
    "paypal.com",
    "square.com",
    "coinbase.com",
    "robinhood.com",
    # E-commerce
    "shopify.com",
    "woocommerce.com",
    "bigcommerce.com",
    "etsy.com",
    "ebay.com",
    # Marketing
    "mailchimp.com",
    "hubspot.com",
    "salesforce.com",
    "zendesk.com",
    "intercom.com",
    # Media
    "medium.com",
    "substack.com",
    "wordpress.org",
    "ghost.org",
    # Other
    "wikipedia.org",
    "reddit.com",
    "twitter.com",
    "linkedin.com",
    "producthunt.com",
]

print("Domain Arm Assignment (50/50 split):\n")
print("=" * 60)

treatment_sites = []
control_sites = []

for domain in domains:
    arm = get_arm(domain)
    if arm == "TREATMENT":
        treatment_sites.append(domain)
    else:
        control_sites.append(domain)

print(f"TREATMENT ({len(treatment_sites)} sites):")
for site in treatment_sites:
    print(f"  + {site}")

print(f"\nCONTROL ({len(control_sites)} sites):")
for site in control_sites:
    print(f"  - {site}")

print("\n" + "=" * 60)
print("\nTo run treatment audits, use these domains:")
for site in treatment_sites[:10]:
    print(f"  python scripts/direct_audit_test.py {site}")
