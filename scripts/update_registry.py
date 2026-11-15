
import json
import os
import re
import urllib.request
from urllib.parse import quote

OWNER = os.environ["GITHUB_OWNER"]
CURRENT_REPO = os.environ["CURRENT_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]

API = "https://api.github.com"

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Cinnamon-Desklets-Registry"
}

if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"


def get_json(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def get_text(url):
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def get_repositories():
    owner_info = get_json(f"{API}/users/{OWNER}")

    if owner_info.get("type") == "Organization":
        endpoint = f"{API}/orgs/{OWNER}/repos"
    else:
        endpoint = f"{API}/users/{OWNER}/repos"

    repositories = []
    page = 1

    while True:
        batch = get_json(
            f"{endpoint}?per_page=100&page={page}&sort=full_name"
        )

        if not batch:
            break

        repositories.extend(batch)
        page += 1

    return repositories


def scan_desklets(repositories):
    desklets = []

    for repo in repositories:
        full_name = repo["full_name"]

        if full_name.lower() == CURRENT_REPO.lower():
            continue

        if repo.get("archived"):
            continue

        branch = quote(repo["default_branch"], safe="")

        manifest_url = (
            f"https://raw.githubusercontent.com/"
            f"{full_name}/{branch}/manifest.json"
        )

        try:
            manifest = json.loads(get_text(manifest_url))

            name = manifest.get("name")
            version = manifest.get("version")
            description = manifest.get("description")

            if not all(
                isinstance(value, str) and value.strip()
                for value in (name, version, description)
            ):
                print(f"Skipping invalid manifest: {full_name}")
                continue

            desklets.append({
                "name": name.strip(),
                "version": version.strip(),
                "description": description.strip(),
                "url": repo["html_url"]
            })

            print(f"Found desklet: {name} ({version})")

        except Exception as error:
            print(f"Skipping {full_name}: {error}")

    return sorted(
        desklets,
        key=lambda item: item["name"].lower()
    )


def generate_projects(desklets):
    if not desklets:
        return "", "No desklets have been published yet."

    intro = (
        "Explore the repositories to discover available desklets, "
        "their features, installation instructions, and source code."
    )

    lines = []

    for desklet in desklets:
        name = desklet["name"]
        version = desklet["version"]
        url = desklet["url"]

        description = re.sub(
            r"\s+", " ", desklet["description"]
        ).replace("|", r"\|")

        lines.extend([
            f"### [{name}]({url})",
            "",
            f"**Version:** `{version}`",
            "",
            description,
            ""
        ])

    return intro, "\n".join(lines).strip()


def update_readme(intro, projects_content, desklet_count):
    readme_path = "README.md"

    with open(readme_path, "r", encoding="utf-8") as file:
        readme = file.read()

    # Update the Projects introduction.
    intro_pattern = (
        r"(## Projects\s*\n).*?"
        r"(?=<!-- PROJECTS_LIST_START -->)"
    )

    updated_readme, intro_count = re.subn(
        intro_pattern,
        lambda match: (
            match.group(1)
            + (intro + "\n\n" if intro else "")
        ),
        readme,
        count=1,
        flags=re.DOTALL
    )

    if intro_count != 1:
        raise RuntimeError(
            "Could not find the Projects section in README.md."
        )

    # Update the projects list.
    projects_pattern = (
        r"(<!-- PROJECTS_LIST_START -->)"
        r".*?"
        r"(<!-- PROJECTS_LIST_END -->)"
    )

    updated_readme, projects_count = re.subn(
        projects_pattern,
        lambda match: (
            match.group(1)
            + "\n\n"
            + projects_content
            + "\n\n"
            + match.group(2)
        ),
        updated_readme,
        count=1,
        flags=re.DOTALL
    )

    if projects_count != 1:
        raise RuntimeError(
            "Could not find README project list markers."
        )

    if updated_readme == readme:
        print("README is already up to date.")
        return

    with open(readme_path, "w", encoding="utf-8") as file:
        file.write(updated_readme)

    print(f"README updated with {desklet_count} desklets.")


def main():
    repositories = get_repositories()

    print(f"Found {len(repositories)} repositories.")

    desklets = scan_desklets(repositories)

    intro, projects_content = generate_projects(desklets)

    update_readme(
        intro,
        projects_content,
        len(desklets)
    )


if __name__ == "__main__":
    main()
