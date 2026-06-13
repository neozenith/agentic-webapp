import { X } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import {
  type Directory,
  fetchDirectory,
  listShareableGroups,
  type ShareableGroup,
  type ShareEdit,
  shareAsset,
  shareFolder,
} from "../api";

/** What the dialog is sharing — a file or a folder — plus its current ACL state. */
export interface ShareTarget {
  kind: "asset" | "folder";
  id: string;
  name: string;
  sharedUserIds: string[];
  sharedGroupIds: string[];
}

interface PermissionsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  target: ShareTarget | null;
  onSaved: () => void;
}

/** A modal to manage who a file or folder is shared with. On open it loads the user
 * directory + groups; on save it diffs the desired state into a ShareEdit change-set
 * and POSTs it to the asset or folder share endpoint. */
export function PermissionsDialog({ open, onOpenChange, target, onSaved }: PermissionsDialogProps) {
  const [directory, setDirectory] = useState<Directory>({});
  const [groups, setGroups] = useState<ShareableGroup[]>([]);
  const [removeUserIds, setRemoveUserIds] = useState<Set<string>>(new Set());
  const [removeGroupIds, setRemoveGroupIds] = useState<Set<string>>(new Set());
  const [pendingEmails, setPendingEmails] = useState<string[]>([]);
  const [pickedGroupIds, setPickedGroupIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // (Re)load directory + groups and reset the pending change-set each time the dialog
  // opens for a target. Guard against setting state after the dialog closed/unmounted.
  useEffect(() => {
    if (!open || !target) return;
    let cancelled = false;
    setError(null);
    setRemoveUserIds(new Set());
    setRemoveGroupIds(new Set());
    setPendingEmails([]);
    setPickedGroupIds(new Set());
    Promise.all([fetchDirectory(), listShareableGroups()])
      .then(([dir, grps]) => {
        if (cancelled) return;
        setDirectory(dir);
        setGroups(grps);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [open, target]);

  // Escape closes the dialog (overlay click + the Close button are the other exits).
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  if (!open || !target) return null;

  const remainingUsers = target.sharedUserIds.filter((u) => !removeUserIds.has(u));
  const remainingGroups = target.sharedGroupIds.filter((g) => !removeGroupIds.has(g));
  const groupName = (gid: string) => groups.find((g) => g.group_id === gid)?.name ?? gid;

  // Suggestions for the user combobox: every directory identity not already shared-with and
  // not already queued — matchable by name or email, value carried as the email to add.
  const sharedEmails = new Set(
    remainingUsers.map((uid) => directory[uid]?.email).filter((e): e is string => Boolean(e)),
  );
  const userOptions: ComboboxOption[] = Object.values(directory)
    .filter((u) => !sharedEmails.has(u.email) && !pendingEmails.includes(u.email))
    .map((u) => ({ value: u.email, label: u.name, hint: u.email }));

  // Suggestions for the group combobox: groups not already shared-with and not already queued.
  const groupOptions: ComboboxOption[] = groups
    .filter((g) => !target.sharedGroupIds.includes(g.group_id) && !pickedGroupIds.has(g.group_id))
    .map((g) => ({ value: g.group_id, label: g.name }));

  const addEmail = (raw: string) => {
    const email = raw.trim();
    if (email) setPendingEmails((prev) => (prev.includes(email) ? prev : [...prev, email]));
  };
  const addGroup = (gid: string) => setPickedGroupIds((prev) => new Set(prev).add(gid));

  const removeUser = (uid: string) => setRemoveUserIds((prev) => new Set(prev).add(uid));
  const removeGroup = (gid: string) => setRemoveGroupIds((prev) => new Set(prev).add(gid));
  const removePending = (email: string) => setPendingEmails((prev) => prev.filter((e) => e !== email));
  const removePickedGroup = (gid: string) =>
    setPickedGroupIds((prev) => {
      const next = new Set(prev);
      next.delete(gid);
      return next;
    });

  const handleSave = async () => {
    const edit: ShareEdit = {};
    if (pendingEmails.length) edit.add_user_emails = pendingEmails;
    if (removeUserIds.size) edit.remove_user_ids = [...removeUserIds];
    if (pickedGroupIds.size) edit.add_group_ids = [...pickedGroupIds];
    if (removeGroupIds.size) edit.remove_group_ids = [...removeGroupIds];
    setSaving(true);
    setError(null);
    try {
      if (target.kind === "asset") await shareAsset(target.id, edit);
      else await shareFolder(target.id, edit);
      onSaved();
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-black/50"
        onClick={() => onOpenChange(false)}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Share ${target.name}`}
        className="relative z-10 flex max-h-[85vh] w-full max-w-md flex-col gap-4 overflow-auto rounded-xl border border-border bg-card p-5 text-card-foreground shadow-lg"
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold leading-none">Share</h2>
            <p className="mt-1 truncate text-sm text-muted-foreground">{target.name}</p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            aria-label="Close"
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" />
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">⚠️ {error}</p>}

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">People with access</h3>
          {remainingUsers.length === 0 && pendingEmails.length === 0 ? (
            <p className="text-xs text-muted-foreground">Not shared with anyone yet.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {remainingUsers.map((uid) => (
                <li key={uid} className="flex items-center gap-2 text-sm">
                  <span className="truncate">{directory[uid]?.name ?? uid}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="ml-auto size-6"
                    aria-label={`Remove ${directory[uid]?.name ?? uid}`}
                    onClick={() => removeUser(uid)}
                  >
                    <X className="size-3.5" />
                  </Button>
                </li>
              ))}
              {pendingEmails.map((email) => (
                <li key={email} className="flex items-center gap-2 text-sm">
                  <span className="truncate">{email}</span>
                  <Badge variant="muted">new</Badge>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="ml-auto size-6"
                    aria-label={`Remove ${email}`}
                    onClick={() => removePending(email)}
                  >
                    <X className="size-3.5" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <Combobox
            label="Add by name or email"
            placeholder="Add by name or email"
            options={userOptions}
            onSelect={addEmail}
            onFreeText={addEmail}
            emptyText="No matching people — press Enter to add this email"
          />
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-medium">Groups with access</h3>
          {remainingGroups.length === 0 && pickedGroupIds.size === 0 ? (
            <p className="text-xs text-muted-foreground">No groups yet.</p>
          ) : (
            <ul className="flex flex-col gap-1">
              {remainingGroups.map((gid) => (
                <li key={gid} className="flex items-center gap-2 text-sm">
                  <span className="truncate">{groupName(gid)}</span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="ml-auto size-6"
                    aria-label={`Remove group ${groupName(gid)}`}
                    onClick={() => removeGroup(gid)}
                  >
                    <X className="size-3.5" />
                  </Button>
                </li>
              ))}
              {[...pickedGroupIds].map((gid) => (
                <li key={gid} className="flex items-center gap-2 text-sm">
                  <span className="truncate">{groupName(gid)}</span>
                  <Badge variant="muted">new</Badge>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="ml-auto size-6"
                    aria-label={`Remove group ${groupName(gid)}`}
                    onClick={() => removePickedGroup(gid)}
                  >
                    <X className="size-3.5" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
          <Combobox label="Add a group" placeholder="Add a group" options={groupOptions} onSelect={addGroup} />
        </section>

        <div className="mt-1 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" disabled={saving} onClick={() => void handleSave()}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
