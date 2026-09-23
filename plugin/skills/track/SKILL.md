---
name: track
description: Record what happened with job applications from plain language — "Acme rejected me", "phone screen with Globex Tuesday", "I applied to Initech's SRE role yesterday" — or report what's open and which follow-ups are due. Use whenever the user mentions news about an application or asks where things stand.
argument-hint: <what happened, or "status">
---

# Track applications

Keep `applications/*.md` accurate using the `jobsmith apps` commands, which validate the data and
log history. Don't hand-edit the frontmatter unless no command covers the change (e.g.
adding a contact); if you do, run `jobsmith check` after.

## Where things stand

For "what's open", "status" or "what should I follow up on":

```bash
jobsmith apps due          # follow-ups due today or earlier
jobsmith apps list --open  # everything in progress
```

Summarise briefly. Lead with anything due, then group by status. Offer to draft follow-up
messages for due items, but don't send anything.

## Recording news

1. **Find the application.** Use `jobsmith apps update <words>`, which matches words against
   the company and role. If it reports several matches, ask which one. If none matches and the
   user is describing a new application, create it:
   `jobsmith apps add --company "…" --role "…" [--url …] [--status applied]`.
2. **Turn dates into ISO dates.** Resolve "yesterday" or "Tuesday" relative to today's date and
   say the date you used back to the user.
3. **Update.** One command can set the status, log an event and set the follow-up:

   | News | Command |
   |---|---|
   | Applied | `--status applied --followup +7d` (add `--on <date>` if it wasn't today) |
   | Recruiter reached out / screen scheduled | `--status screening --event "Recruiter screen scheduled for <date>" --followup <day after the screen>` |
   | Interview scheduled | `--status interviewing --event "<round> interview on <date>" --followup <day after>` |
   | Interview done | `--event "<round> interview with <names>" --followup +5d` |
   | Offer | `--status offer --event "Offer: <key terms if given>"` |
   | Rejected | `--status rejected --event "<how they heard, if said>"` |
   | No reply for a long time | `--status ghosted` (confirm with the user first) |
   | Withdrew | `--status withdrawn --event "<reason if given>"` |
   | Followed up | `--event "Followed up by <email/LinkedIn>" --followup +7d` |

   Closed statuses (offer, rejected, ghosted, withdrawn) clear the follow-up automatically.
4. **Details worth keeping** go in the notes section of the file: interviewer names, what was
   discussed, salary figures, next steps. Add people who'll matter again under `contacts`.
5. **Confirm** in one line per application: new status and next follow-up.

Several updates in one message are fine. Handle each one, then give a single summary.
