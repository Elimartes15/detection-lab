# Scenario 001 · PowerShell Launched With an Encoded Command

| | |
| --- | --- |
| **Date** | 2026-11-01 |
| **MITRE ATT&CK** | [T1059.001 PowerShell](https://attack.mitre.org/techniques/T1059/001/) (Execution) · [T1027 Obfuscated Files or Information](https://attack.mitre.org/techniques/T1027/) (Defense Evasion) |
| **Target** | WS02 (Windows 11 Enterprise, `cybereli.local`) |
| **Data sources** | Sysmon Event ID 1, Windows Security 4688, PowerShell Operational 4104 |
| **Credit** | Adapted from SigmaHQ's [Suspicious Execution of Powershell with Base64](https://github.com/SigmaHQ/sigma/blob/master/rules/windows/process_creation/proc_creation_win_powershell_encode.yml) (frack113) |
| **Detection** | [Sigma](../../detections/sigma/windows/process_creation/proc_creation_win_powershell_encoded_command.yml) · [Elastic EQL](../../detections/elastic/proc_creation_win_powershell_encoded_command.eql) · [Microsoft Defender KQL](../../detections/kql/proc_creation_win_powershell_encoded_command.kql) |
| **Result** | Detected. 4 alerts (2 runs × 2 sources), triaged in a case; alerts closed as test true positives |

## Hypothesis

Attackers Base64-encode PowerShell commands (`-EncodedCommand`) so the real instructions never appear in plain text on the command line. That hides them from casual review and from simple keyword filters. Legitimate interactive use of encoded commands is rare, so **a PowerShell process started with `-EncodedCommand` or any of its abbreviations is worth an alert**, and script block logging should reveal what was actually run.

## Emulation

A benign payload, launched the way an attacker would launch a real one:

```powershell
$cmd = 'Write-Output "scenario-001"; whoami'
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))
powershell.exe -NoProfile -EncodedCommand $b64
powershell.exe -NoProfile -enc $b64
```

Two runs: the full parameter name, and the short `-enc` form attackers commonly use. The payload only prints a line and runs `whoami` (itself a discovery technique, T1033).

## Telemetry

The same action, seen from three independent sources:

| Source | Event | What it shows |
| --- | --- | --- |
| Sysmon | Event ID 1 (process creation) | `powershell.exe` with the Base64 blob in `process.command_line`, its parent process, and process GUIDs that link parent to child |
| Windows Security | 4688 (process creation) | The same launch and command line, independently of Sysmon |
| PowerShell Operational | 4104 (script block) | **The decoded command**: `Write-Output "scenario-001"; whoami` |

![4104 showing the decoded command](evidence/01-4104-decoded.png)

**The encoding hid nothing.** PowerShell has to decode a command before running it, and script block logging records the decoded version.

## Detection logic

Match a PowerShell binary, identified by path **or** by its original file name (so a renamed copy is still caught in Sysmon data), whose command line contains the encoded-command parameter or any abbreviation PowerShell accepts: `-e`, `-en`, `-enc`, `-enco…`, `-ec`.

The flag list comes from SigmaHQ's rule. My changes:
- I added the `windash` modifier, which also matches `/enc` and Unicode dash variants.
- I added `OriginalFileName`, so a renamed `powershell.exe` is still caught.

- **Sigma** is the source of truth, converted with pySigma (`ecs_windows` pipeline) to **EQL** for Elastic and to **KQL** for Microsoft Defender (`DeviceProcessEvents`).
- **EQL** was chosen over Lucene because its `like~` operator is **case-insensitive**: `-ENC`, `-Enc` and `-enc` all match. Attackers vary case to evade case-sensitive string matches.
- Elastic rule: Event Correlation (EQL), index patterns `logs-windows.sysmon_operational-*` and `logs-system.security-*`, severity Medium, risk score 47.

![Rule revision 0](evidence/03-rule-revision-0.png)

*Revision 0, the rule as first deployed: the converted query unchanged, plus a `logs-*` index pattern. Revision 1 removed `logs-*` and simplified the field name (see [lessons learned](#lessons-learned)).*

## Validation

The emulation produced **4 alerts** from revision 0: 2 runs × 2 sources. The 2 alerts with the Analyzer icon are Sysmon; the other 2 are Security log 4688 (`system.security`).

![Alerts](evidence/04-alerts.png)

The alert reason reads: *process event with process powershell.exe, parent process powershell.exe, by administrator on ws02*.

![Alert detail](evidence/02-alert-detail.png)

*The rule page shows revision 1 because it was edited after this run. The alerts in it came from revision 0, at 15:58:36.*

Elastic's **Analyzer** rebuilt the process tree from Sysmon's process GUIDs:

```
powershell.exe               (interactive session)
  └─ powershell.exe -EncodedCommand …    ← alerted event
       └─ whoami.exe   342 ms later      ← the decoded payload running
```

![Analyzer process tree](evidence/05-analyzer.png)

The tree shows cause and effect without decoding anything: the encoded command is what started `whoami.exe`. In a real incident the top node is the story: `WINWORD.EXE` or `OUTLOOK.EXE` there would point to a malicious document.

The alerts were attached to a case with the decoded command in its description, then closed as test true positives.

![Case](evidence/06-case.png)

*The case while in progress.*

## Tuning and false positives

- **Duplicate alerts:** each execution alerts twice, once per source. Kept deliberately: if an attacker unloads the Sysmon driver, the Security-log alert still fires. Elastic's alert suppression could merge them; not tested yet.
- **Only Sysmon alerts open in the Analyzer.** 4688 events carry no process GUIDs. Sysmon provides context; 4688 provides resilience.
- **Likely false positives:** management and deployment tools that pass scripts as encoded commands (SCCM, Intune, some installers). None seen in the lab yet; in production, baseline for a week and add exceptions by parent process and signer, not by command line.
- **`-Encoding` false positive:** ` -enco` also matches the unrelated `-Encoding` parameter (for example `Get-Content log.txt -Encoding UTF8`). Revision 2 excluded it the way SigmaHQ does, and that exclusion turned out to be a bypass. See [Revision 2](#revision-2-the-filter-that-opened-a-hole).
- **Inconsistent user names across sources:** the same account appears as `administrator` in one source and `Administrator` in the other, so the case counted 2 associated users for 1 account. Queries and correlations on `user.name` should be case-insensitive.

## Revision 2: the filter that opened a hole

Revision 2 (2026-11-04) added SigmaHQ's exclusion, `CommandLine|contains: ' -Encoding '`, and was the first change shipped through the [detection-as-code pipeline](../../README.md#detection-as-code-pipeline): branch, `sigma check`, automatic EQL/KQL conversion, merge request. Tested on `ws02`:

| # | Command | Expected | Result |
| --- | --- | --- | --- |
| 1 | `powershell.exe -NoProfile -enc $b64` | Alert | ✅ Alerted (Sysmon + 4688) |
| 2 | `powershell.exe -NoProfile -Command "Get-Content C:\Windows\win.ini -Encoding UTF8 \| Out-Null"` | No alert | ✅ No alert |
| 3 | `powershell.exe -NoProfile -enc $b64 -Encoding x` | Bypass? | ✅ Not a bypass: PowerShell rejects trailing text after `-EncodedCommand` |
| 4 | `powershell.exe -NoProfile -WorkingDirectory "C:\Temp\x -Encoding y" -enc $b64` | Bypass? | ❌ **Bypass:** payload ran, no alert |

**The exclusion matches a string the attacker controls.** Any valid parameter value containing ` -Encoding `, here a folder name, silences the rule. Test 3 alone would have suggested the filter was safe; the bypass needed a *valid* parameter to carry the string.

**Revision 3 plan:** remove the exclusion and make the match precise. Every abbreviation of `-EncodedCommand` from `-enco` on is `-enco`, `-encod` or `-encode…`, while `-Encoding` starts with `-encodi`. Matching ` -enco `, ` -encod ` and ` -encode` instead of ` -enco` removes the false positive without leaving an attacker-controlled exclusion.

## Gaps

| Evasion | Covered? | Next step |
| --- | --- | --- |
| Case variations (`-ENC`) | Yes, EQL `like~` | — |
| Renamed `powershell.exe` | Sysmon: yes (`OriginalFileName`). 4688: no | Accept; Sysmon covers it |
| PowerShell hosted inside another program (no `powershell.exe` at all) | No | **A 4104-based rule**: script block logging records the code regardless of the host process |
| Payload passed another way (download cradle, `-Command` with obfuscation) | No | Separate rules for obfuscation patterns in 4104 |
| ` -Encoding ` planted in another parameter value (rev 2) | **No** (bypass confirmed) | Rev 3: precise flag list, no exclusion |

**Not yet tested:** the emulation ran as the built-in domain Administrator on a workstation, which no real environment should allow. A run as a standard domain user is still pending; a workstation admin model (LAPS) is on the roadmap.

## Lessons learned

1. **Test a hypothesis before changing the rule.** The converted query used `process.executable.caseless`. I assumed that field only existed in Elastic Defend data and changed it to `process.executable`. The evidence said otherwise: revision 0 had already fired on Security-log events, and 6,764 4688 events in two days carry the field. The edit was harmless, because `like~` already ignores case. But it was a fix for a problem that didn't exist. A ten-second Discover query would have answered it, and the CI pipeline's validation step will run that check automatically.
2. **Discover doesn't run EQL.** Discover's search bar accepts KQL and Lucene only; EQL is tested in the rule preview or a Timeline's Correlation tab.
3. **Scope rules to the data they need.** The rule first included `logs-*`, which searches every data stream in the cluster. Revision 1 narrowed it to the two relevant patterns.
4. **Two sources are worth the duplicates.** One gives context (process tree), the other resilience.
