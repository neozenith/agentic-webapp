import type * as React from "react";
import { useId, useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface ComboboxOption {
  value: string;
  label: string;
  /** Secondary searchable + displayed text (e.g. an email shown under a name). */
  hint?: string;
}

interface ComboboxProps {
  /** Accessible name for the text input and its listbox. */
  label: string;
  placeholder?: string;
  options: ComboboxOption[];
  /** Called with an option's value when the user picks a suggestion. */
  onSelect: (value: string) => void;
  /** When set, pressing Enter on text that matches no option submits the raw text. */
  onFreeText?: (text: string) => void;
  emptyText?: string;
}

/** A minimal accessible combobox (WAI-ARIA combobox + listbox pattern) built on the shared
 * Input: type to filter `options` live, arrow/Enter or click to select — no heavy deps.
 * Matching is client-side over label + hint, so the caller fetches its list once. */
export function Combobox({
  label,
  placeholder,
  options,
  onSelect,
  onFreeText,
  emptyText = "No matches",
}: ComboboxProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.label.toLowerCase().includes(q) || (o.hint ?? "").toLowerCase().includes(q));
  }, [options, query]);

  const choose = (option: ComboboxOption): void => {
    onSelect(option.value);
    setQuery("");
    setOpen(false);
    setActive(0);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((i) => Math.min(i + 1, Math.max(matches.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      const picked = matches[active];
      if (open && picked) {
        e.preventDefault();
        choose(picked);
      } else if (onFreeText && query.trim()) {
        e.preventDefault();
        onFreeText(query.trim());
        setQuery("");
        setOpen(false);
      }
    }
  };

  const activeId = open && matches[active] ? `${listId}-opt-${active}` : undefined;

  return (
    <div className="relative">
      <Input
        type="text"
        role="combobox"
        aria-label={label}
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        autoComplete="off"
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      {open && (
        <div
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute z-20 mt-1 max-h-48 w-full overflow-auto rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {matches.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">{emptyText}</p>
          ) : (
            matches.map((o, i) => (
              <button
                key={o.value}
                type="button"
                id={`${listId}-opt-${i}`}
                role="option"
                aria-selected={i === active}
                tabIndex={-1}
                // Keep focus on the input so onBlur doesn't close the list before the click lands.
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => choose(o)}
                className={cn(
                  "flex w-full flex-col items-start rounded-sm px-2 py-1.5 text-left text-sm",
                  i === active ? "bg-accent text-accent-foreground" : "hover:bg-accent/50",
                )}
              >
                <span className="truncate">{o.label}</span>
                {o.hint && <span className="truncate text-xs text-muted-foreground">{o.hint}</span>}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
