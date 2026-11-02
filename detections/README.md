# Detections

Sigma is the source of truth. Each rule is converted with pySigma: to EQL for Elastic Security, and to KQL for Microsoft Defender / Sentinel. Every rule is validated against real telemetry before it counts as done.

| Rule | ATT&CK | Sigma | Elastic | KQL | Scenario |
| --- | --- | --- | --- | --- | --- |
| PowerShell Launched With an Encoded Command | T1059.001, T1027 | [yml](sigma/windows/process_creation/proc_creation_win_powershell_encoded_command.yml) | [eql](elastic/proc_creation_win_powershell_encoded_command.eql) | [kql](kql/proc_creation_win_powershell_encoded_command.kql) | [001](../scenarios/001-powershell-encoded-command/README.md) |
