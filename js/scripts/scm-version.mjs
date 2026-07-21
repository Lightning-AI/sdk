import { spawnSync } from "node:child_process";

const TAG_PATTERN = /^v(\d{4})\.(\d{2})\.(\d{2})(?:\.post(\d+))?$/;
const DESCRIBE_PATTERN = /^(.*)-(\d+)-g([0-9a-f]+)(-dirty)?$/;

function git(repositoryRoot, args, allowFailure = false) {
  const result = spawnSync("git", args, {
    cwd: repositoryRoot,
    encoding: "utf8",
  });

  if (result.error) {
    throw new Error(`unable to run Git: ${result.error.message}`);
  }
  if (result.status !== 0 && !allowFailure) {
    const detail = result.stderr.trim() || result.stdout.trim() || `exit code ${result.status}`;
    throw new Error(`unable to read Git repository state: ${detail}`);
  }
  return result;
}

function utcDateStamp(date) {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

export function parseTag(tag) {
  const match = TAG_PATTERN.exec(tag);
  if (!match) {
    throw new Error(`unsupported version tag: ${tag}`);
  }

  const [, yearText, monthText, dayText, postText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    throw new Error(`unsupported version tag: ${tag}`);
  }

  return {
    raw: tag,
    year,
    month,
    day,
    post: postText === undefined ? null : Number(postText),
  };
}

export function parseDescribe(raw) {
  const value = raw.trim();
  const match = DESCRIBE_PATTERN.exec(value);
  if (!match) {
    throw new Error(`unable to parse Git description: ${value}`);
  }

  const [, tagText, distanceText, hash, dirtyText] = match;
  return {
    tag: parseTag(tagText),
    distance: Number(distanceText),
    hash,
    dirty: dirtyText !== undefined,
  };
}

export function renderVersion(description, date = new Date()) {
  const metadata = `g${description.hash}${description.dirty ? `.d${utcDateStamp(date)}` : ""}`;

  if (description.tag === null) {
    return `0.0.0-dev.${description.distance}+${metadata}`;
  }

  const { year, month, day, post } = description.tag;
  const core = `${year}.${month}.${day}`;
  if (description.distance === 0 && !description.dirty) {
    return post === null ? core : `${core}-post${post}`;
  }

  if (post !== null) {
    return `${core}-post${post + 1}.dev.${description.distance}+${metadata}`;
  }
  return `${year}.${month}.${day + 1}-dev.${description.distance}+${metadata}`;
}

export function describeRepository(repositoryRoot = process.cwd()) {
  const described = git(
    repositoryRoot,
    ["describe", "--tags", "--long", "--dirty", "--match", "v[0-9]*"],
    true,
  );
  if (described.status === 0) {
    return parseDescribe(described.stdout);
  }

  git(repositoryRoot, ["rev-parse", "--is-inside-work-tree"]);
  const distance = Number(git(repositoryRoot, ["rev-list", "--count", "HEAD"]).stdout.trim());
  const hash = git(repositoryRoot, ["rev-parse", "--short", "HEAD"]).stdout.trim();
  const dirty = git(repositoryRoot, ["diff-index", "--quiet", "HEAD", "--"], true).status !== 0;
  return { tag: null, distance, hash, dirty };
}

export function assertRelease(description) {
  if (description.tag === null) {
    throw new Error("release packaging requires a matching version tag");
  }
  if (description.distance !== 0) {
    throw new Error("release packaging requires HEAD to be exactly at the version tag");
  }
  if (description.dirty) {
    throw new Error("release packaging requires a clean worktree");
  }
}
