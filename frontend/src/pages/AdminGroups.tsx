import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createGroup, type Directory, deleteGroup, fetchDirectory, type Group, listGroups, updateGroup } from "../api";

// Split a comma/space-separated email list into a clean array of addresses.
const parseEmails = (raw: string): string[] =>
  raw
    .split(/[\s,]+/)
    .map((e) => e.trim())
    .filter(Boolean);

// Resolve a pseudonymous member_id to "name <email>" when the directory knows it,
// else show the raw id truncated to its first 8 chars.
const memberLabel = (memberId: string, dir: Directory): string => {
  const known = dir[memberId];
  return known ? `${known.name} <${known.email}>` : `${memberId.slice(0, 8)}…`;
};

export function AdminGroups() {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [directory, setDirectory] = useState<Directory>({});
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [members, setMembers] = useState("");
  // Per-group "add member" inputs, keyed by group_id.
  const [addEmail, setAddEmail] = useState<Record<string, string>>({});

  // Any mutation re-fetches BOTH groups and the directory so member labels stay resolved.
  const refresh = () =>
    Promise.all([listGroups(), fetchDirectory()])
      .then(([g, d]) => {
        setGroups(g);
        setDirectory(d);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));

  // biome-ignore lint/correctness/useExhaustiveDependencies: intentional mount-only load
  useEffect(() => {
    void refresh();
  }, []);

  const create = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    createGroup(trimmed, parseEmails(members))
      .then(() => {
        setName("");
        setMembers("");
        return refresh();
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };

  const addMembers = (groupId: string) => {
    const emails = parseEmails(addEmail[groupId] ?? "");
    if (emails.length === 0) return;
    updateGroup(groupId, { add_member_emails: emails })
      .then(() => {
        setAddEmail((prev) => ({ ...prev, [groupId]: "" }));
        return refresh();
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };

  const removeMember = (groupId: string, memberId: string) => {
    updateGroup(groupId, { remove_member_ids: [memberId] })
      .then(refresh)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };

  const remove = (groupId: string) => {
    deleteGroup(groupId)
      .then(refresh)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };

  if (error) return <p className="text-destructive">⚠️ {error}</p>;
  if (!groups) return <p className="text-muted-foreground">Loading groups…</p>;

  return (
    <section className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between gap-2">
          <CardTitle>Custom groups</CardTitle>
          <Button asChild variant="outline" size="sm">
            <Link to="/admin">Back to admin</Link>
          </Button>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="Group name"
            aria-label="Group name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-8 w-48"
          />
          <Input
            placeholder="Member emails (comma or space separated)"
            aria-label="Member emails"
            value={members}
            onChange={(e) => setMembers(e.target.value)}
            className="h-8 w-80"
          />
          <Button size="sm" onClick={create}>
            Create group
          </Button>
        </CardContent>
      </Card>

      {groups.length === 0 ? (
        <p className="text-muted-foreground">No groups yet.</p>
      ) : (
        groups.map((g) => (
          <Card key={g.group_id}>
            <CardHeader className="flex-row items-center justify-between gap-2">
              <div className="flex flex-col">
                <CardTitle>{g.name}</CardTitle>
                <span className="text-sm text-muted-foreground">
                  created {new Date(g.created_at).toLocaleDateString()}
                </span>
              </div>
              <Button variant="destructive" size="sm" onClick={() => remove(g.group_id)}>
                Delete group
              </Button>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-1">
                {g.member_ids.length === 0 ? (
                  <span className="text-sm text-muted-foreground">No members</span>
                ) : (
                  g.member_ids.map((mid) => (
                    <Badge key={mid} variant="secondary">
                      {memberLabel(mid, directory)}
                      <button
                        type="button"
                        aria-label={`Remove ${memberLabel(mid, directory)}`}
                        className="ml-1 hover:text-destructive"
                        onClick={() => removeMember(g.group_id, mid)}
                      >
                        ×
                      </button>
                    </Badge>
                  ))
                )}
              </div>
              <div className="flex items-center gap-2">
                <Input
                  placeholder="Add member email(s)"
                  aria-label={`Add member to ${g.name}`}
                  value={addEmail[g.group_id] ?? ""}
                  onChange={(e) => setAddEmail((prev) => ({ ...prev, [g.group_id]: e.target.value }))}
                  className="h-8 w-72"
                />
                <Button size="sm" variant="outline" onClick={() => addMembers(g.group_id)}>
                  Add
                </Button>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </section>
  );
}
