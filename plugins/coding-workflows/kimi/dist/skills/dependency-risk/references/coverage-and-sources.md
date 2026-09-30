# Dependency Coverage and Sources

## What the helper measures

`scripts/dep_inventory.py` reads npm `package-lock.json` or
`npm-shrinkwrap.json` with `lockfileVersion` 2 or 3. Field meanings follow npm's
package-lock documentation (checked against the documentation bundled with npm
10.9.7): the `packages` map is keyed by install location, the root project is
the `""` key, and entries carry `version`, `resolved`, `integrity`, `link`,
`dev`, `optional`, `devOptional`, `inBundle`, `hasInstallScript`, and fields
copied from each package's `package.json`.

| Fact | How it is derived |
| --- | --- |
| Declared | `package.json` sections `dependencies`, `devDependencies`, `optionalDependencies`, `peerDependencies`. |
| Resolved | Lockfile `packages` entries with their exact versions. |
| Direct | Named in the lockfile root entry and installed at `node_modules/<name>`. A top-level location alone does not make a package direct, because hoisting places transitive packages there. |
| Transitive | Every other installed package. |
| Source | `registry` (tarball on a registry host), `git`, `tarball` (other URL), `file`, `link`, `workspace`, `bundled`, or `unknown`. |
| Install-time code | `hasInstallScript`: the package has a `preinstall`, `install`, or `postinstall` script. |
| Integrity | Presence of an `integrity` hash for registry and tarball sources. |
| Lock drift | Differences between `package.json` and the lockfile root entry. |

## Coverage per check

| Check | `clear` means | Common `not checked` or `blocked` reasons |
| --- | --- | --- |
| `install-script` | No resolved package declares install scripts. | No lockfile, or lockfile version 1. |
| `resolution-source` | Every package resolves from the public registry, a workspace, or a local link. | Same as above. |
| `integrity` | Every registry or tarball package has an integrity hash. | Same as above. |
| `lock-drift` | `package.json` and the lockfile root agree. | Same as above. |
| `advisories` | Every queryable package was checked and none had a known advisory. | Lookup not authorized, no network, or results did not match the payload. |

Other ecosystems (Python, Rust, Go, Ruby, PHP, .NET, Java, yarn, pnpm, bun) are
listed as `not checked (ecosystem or format not implemented)`. Never summarize a
repository as low-risk from npm checks alone when other ecosystems are present.

## Advisory lookups

The helper never contacts a network service. To check advisories:

1. Run the helper with `--emit-osv-query <file>`. The payload holds only package
   names, versions, and the ecosystem, shaped for the OSV `querybatch` API. Its
   exact current shape was not re-verified in this repository because the OSV
   documentation was not reachable when this skill was written; confirm it
   against the current OSV API documentation before sending.
2. Sending that payload discloses the repository's dependency list to a third
   party. Ask the user before sending it.
3. With authorization, send it with the host's own tools, save the response, and
   rerun the helper with `--osv-results <file>`. Results must correspond to the
   same payload; otherwise the advisory check stays `not checked`.

A single candidate package the user named is not repository-derived data;
looking it up is an ordinary external read.

## Source lanes for a candidate package

When the question is whether to adopt a package that is not yet a dependency,
gather from primary sources: the package's own manifest at the version under
consideration (install scripts, dependencies, license), its source repository
and release history, advisory databases, and registry metadata such as
deprecation and publish history. Record each fact with its source and date.
