
import json
import os
import re
import urllib.request

from urllib.parse import quote, urlparse
from html import escape


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

            screenshot = manifest.get("screenshot")

            if isinstance(screenshot, str) and screenshot.strip():
                screenshot = screenshot.strip()
                parsed = urlparse(screenshot)

                if parsed.scheme in ("http", "https") and parsed.netloc:
                    screenshot_url = screenshot

                elif not parsed.scheme:
                    screenshot_url = (
                        f"https://raw.githubusercontent.com/"
                        f"{full_name}/{branch}/"
                        f"{quote(screenshot.lstrip('/'), safe='/')}"
                    )

                else:
                    screenshot_url = None

            else:
                screenshot_url = None

            desklets.append({
                "name": name.strip(),
                "version": version.strip(),
                "description": description.strip(),
                "url": repo["html_url"],
                "screenshot": screenshot_url
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
        ).replace("|", r"**\|**")

        lines.extend([
            f"### [{name}]({url})",
            "",
            f"**Version:** `{version}`",
            "",
            description,
            ""
        ])

        if desklet.get("screenshot"):
            lines.extend([
                f'<img src="{escape(desklet["screenshot"], quote=True)}" width="300" alt="{escape(name, quote=True)} screenshot">',
                ""
            ])

    return intro, "\n".join(lines).strip()


def update_readme(intro, projects_content, desklet_count):
    readme_path = "README.md"

    with open(readme_path, "r", encoding="utf-8") as file:
        readme = file.read()

    pattern = (
        r"(## Projects\s*\n*)"
        r".*?"
        r"(<!-- PROJECTS_LIST_START -->)"
        r".*?"
        r"(<!-- PROJECTS_LIST_END -->)"
    )

    updated_readme, count = re.subn(
        pattern,
        lambda match: (
            match.group(1)
            + (intro + "\n\n" if intro else "")
            + match.group(2)
            + "\n\n"
            + projects_content
            + "\n\n"
            + match.group(3)
        ),
        readme,
        count=1,
        flags=re.DOTALL
    )

    if count != 1:
        raise RuntimeError(
            "Could not find the Projects section and its markers."
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
