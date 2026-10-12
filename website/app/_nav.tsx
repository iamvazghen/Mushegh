"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV: { head: string; links: [string, string][] }[] = [
  {
    head: "Start",
    links: [
      ["Overview", "/"],
      ["Quick start", "/quickstart"],
      ["Setup & keys", "/setup"],
      ["Install & run", "/run"],
      ["Personalize", "/personalize"],
    ],
  },
  {
    head: "Capabilities",
    links: [
      ["Features", "/features"],
      ["Integrations & tools", "/integrations"],
      ["Tool reference (171)", "/tools"],
      ["External apps (MCP/Composio)", "/apps"],
      ["Obsidian vault & memory", "/vault"],
      ["Objectives & agency", "/objectives"],
      ["Privacy & what it stores", "/privacy"],
      ["Skills (35 playbooks)", "/skills"],
    ],
  },
  {
    head: "Voice & devices",
    links: [
      ["Voice pipeline", "/voice"],
      ["Devices", "/devices"],
      ["Phones (iPhone/Android)", "/phones"],
      ["Remote PC control", "/pc-control"],
    ],
  },
  {
    head: "Runtime",
    links: [
      ["Background work", "/background-work"],
      ["Modes (focus/lockdown/…)", "/modes"],
      ["Protocols (8 routines)", "/protocols"],
      ["Memory care & self-health", "/memory-care"],
      ["LLM providers & failover", "/llm-providers"],
      ["Bots & send-paths", "/bots"],
      ["Fleet delegation", "/fleet"],
    ],
  },
  {
    head: "Concepts",
    links: [
      ["Architecture", "/architecture"],
      ["Networking (Tailnet)", "/networking"],
      ["How it is built & verified", "/engineering"],
    ],
  },
  {
    head: "Operate",
    links: [
      ["Configuration", "/configuration"],
      ["Deployment (VPS + ticker)", "/deployment"],
      ["Production readiness", "/production"],
      ["Security", "/security"],
      ["License", "/license"],
    ],
  },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="sidebar">
      <Link href="/" className="brandrow" style={{ color: "inherit" }}>
        <Image src="/logo.png" alt="Mushegh" width={499} height={236} priority />
        <span className="wm">
          Mushegh<span>.ai</span>
        </span>
        <span className="wave" aria-hidden="true"><i /><i /><i /><i /><i /></span>
      </Link>
      <div className="tag">An assistant you install and talk to.</div>

      {NAV.map((group) => (
        <div key={group.head}>
          <div className="navhead">{group.head}</div>
          <nav>
            {group.links.map(([label, href]) => {
              const active = href === "/" ? path === "/" : path.startsWith(href);
              return (
                <Link key={href + label} href={href} className={active ? "active" : ""}>
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      ))}

      <div className="navhead">Links</div>
      <nav>
        <a href="https://github.com/iamvazghen/OpenWatari" target="_blank" rel="noreferrer">
          GitHub ↗
        </a>
        <a href="https://tailscale.com/" target="_blank" rel="noreferrer">
          Tailscale ↗
        </a>
      </nav>
    </aside>
  );
}