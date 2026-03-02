[compare]: https://github.com/conda/conda-pypi/compare
[new release]: https://github.com/conda/conda-pypi/releases/new
[release docs]: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
[rever docs]: https://regro.github.io/rever-docs
[conda-forge]: https://github.com/conda-forge/conda-pypi-feedstock

# Release Process

> [!NOTE]
> Throughout this document are references to the version number as `X.Y.Z`. Replace this with the correct version number. Do **not** prefix the version with a lowercase `v`.

## 1. Open the release issue.

Create a release issue using the template below. After creating it, pin it for easy access.

<details>
<summary><h3>Release Template</h3></summary>

#### Title:
```markdown
Release `X.Y.Z`
```

#### Body:
```markdown
### Summary

Placeholder for `conda-pypi X.Y.Z` release.

| Pilot | <pilot> |
|---|---|
| Co-pilot | <copilot> |

### Tasks

[milestone]: https://github.com/conda/conda-pypi/milestone/<milestone>
[process]: https://github.com/conda/conda-pypi/blob/main/RELEASE.md
[releases]: https://github.com/conda/conda-pypi/releases
[conda-forge]: https://github.com/conda-forge/conda-pypi-feedstock

- [ ] [Complete outstanding PRs][milestone]
- [ ] Create release PR (see [release process][process])
- [ ] [Publish release][releases]
- [ ] Bump [conda-forge feedstock][conda-forge]
- [ ] Announce release
```

</details>

## 2. Run rever.

<details>
<summary><h2>Rever steps</h2></summary>

1. Clone and `cd` into the repository if you haven't done so already:

    ```bash
    $ git clone git@github.com:conda/conda-pypi.git
    $ cd conda-pypi
    ```

2. Fetch the latest changes and create a versioned branch off `main` for the release PR:

    ```bash
    $ git fetch upstream
    $ git checkout -b changelog-X.Y.Z upstream/main
    ```

3. Run `rever --activities authors --force X.Y.Z`:

    > **Note:**
    > Include `--force` when re-running any rever command for the same version; without it, rever skips already-completed activities.

    ```bash
    $ pixi run -e release rever --activities authors --force X.Y.Z
    ```

    - If rever reports unknown authors, add or update entries in `.authors.yml` (new contributors get a new entry; existing contributors using a new name/email get an `aliases`/`alternate_emails` addition).

    - Verify the result with:

        ```bash
        $ git shortlog -se
        ```

      Compare this list against `AUTHORS.md` and repeat until they match.

4. Review news snippets in `news/` (use Markdown, **not** reStructuredText). Add snippets for any undocumented changes using the `news/TEMPLATE` as a guide, naming files `<PR #>-<short-slug>.md`. Commit when satisfied:

    ```bash
    $ git add news/
    $ git commit -m "Update news"
    ```

5. Ensure the `[//]: # (current developments)` marker is present at the top of `CHANGELOG.md`, then run `rever --activities changelog --force X.Y.Z`:

    ```bash
    $ pixi run -e release rever --activities changelog --force X.Y.Z
    ```

    - If this succeeds, undo the commit so both activities can be run together in the next step:

        ```bash
        $ git reset --hard HEAD~1
        ```

6. Run both activities together so the contributor list is embedded in the changelog entry:

    ```bash
    $ pixi run -e release rever --force X.Y.Z
    ```

7. Use [GitHub's auto-generated release notes][new release] to identify first-time contributors and add `made their first contribution in <URL>` next to their entry in the Contributors section of `CHANGELOG.md`. Commit:

    ```bash
    $ git add CHANGELOG.md
    $ git commit -m "Add first-time contributions"
    ```

8. Push the versioned branch:

    ```bash
    $ git push -u upstream changelog-X.Y.Z
    ```

9. Open the Release PR targeting `main`:

    ```markdown
    ## Description

    ✂️ snip snip ✂️ the making of a new release.

    Xref #<RELEASE ISSUE>
    ```

10. [Create][new release] the release and **save as draft**:

    | Field | Value |
    |---|---|
    | Choose a tag | `X.Y.Z` |
    | Target | `main` |
    | Body | copy/paste from `CHANGELOG.md` |

    > **Note:** Only publish the release after the release PR is merged.

</details>

## 3. Wait for review and approval of the release PR.

## 4. Merge the release PR and publish the release.

Go to the [releases page][new release], add the release notes from `CHANGELOG.md` to the draft, and publish.

## 5. Bump the [conda-forge feedstock][conda-forge].

The `regro-cf-autotick-bot` will usually open a PR automatically. Review and merge it (or push fixes to the autotick branch if needed).

## 6. Announce the release.
