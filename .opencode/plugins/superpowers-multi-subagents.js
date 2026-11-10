// OpenCode plugin: registers this repo's skills, but only when superpowers is installed.
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN_ID = "superpowers-multi-subagents";
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const skillsDir = path.join(repoRoot, "skills");
const router = path.join(skillsDir, "subagent-driven-development-multi", "scripts", "agent-router");

export function superpowersInstalled(run = execFileSync) {
  try {
    run("python3", [router, "upstream-path"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

export function readSkills(dir = skillsDir) {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("."))
    .map((entry) => path.join(dir, entry.name, "SKILL.md"))
    .filter((file) => fs.existsSync(file))
    .map(toSkill);
}

function toSkill(file) {
  const text = fs.readFileSync(file, "utf8");
  const match = text.match(/^---\r?\n(.*?)\r?\n---\r?\n?(.*)$/s);
  const fields = Object.fromEntries(
    (match ? match[1] : "")
      .split(/\r?\n/)
      .map((line) => line.match(/^(name|description):\s*(.*)$/))
      .filter(Boolean)
      .map(([, key, value]) => [key, value.trim()]),
  );
  const id = path.basename(path.dirname(file));
  return {
    id,
    name: fields.name || id,
    ...(fields.description ? { description: fields.description } : {}),
    path: file,
    content: match ? match[2] : text,
  };
}

function warnMissing() {
  console.error(
    `[${PLUGIN_ID}] superpowers is not installed, so these skills are not registered. ` +
      "Install superpowers first, or set SUPERPOWERS_SKILLS_DIR.",
  );
}

// OpenCode V1: add the skills folder to the live config.
export const SuperpowersMultiSubagentsPlugin = async () => ({
  config: async (config) => {
    if (Array.isArray(config.skills)) return; // V2 shape, handled by setup()
    if (!superpowersInstalled()) return warnMissing();
    const paths = ((config.skills ??= {}).paths ??= []);
    if (!paths.includes(skillsDir)) paths.push(skillsDir);
  },
});

function addOne(draft, entry) {
  try {
    draft.add(entry);
  } catch (error) {
    console.error(`[${PLUGIN_ID}] skipped skill "${entry.id}":`, error);
  }
}

// OpenCode V2: register each skill natively. A rejected skill is skipped, never fatal.
async function setup(ctx) {
  if (!ctx?.skill || typeof ctx.skill.transform !== "function") return; // V1-shaped context
  if (!superpowersInstalled()) return warnMissing();
  try {
    const skills = readSkills();
    await ctx.skill.transform((draft) => skills.forEach((entry) => addOne(draft, entry)));
  } catch (error) {
    console.error(`[${PLUGIN_ID}] skill registration failed:`, error);
  }
}

export default { id: PLUGIN_ID, server: SuperpowersMultiSubagentsPlugin, setup };
