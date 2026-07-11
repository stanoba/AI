---
name: pylontech-analysis
description: Perform health and anomaly analysis on Pylontech LiFePo4 battery stacks (e.g., US3000C) using the local Pylontech MCP server, serial console log files, and Prometheus/Grafana metrics retrieved via Grafana MCP server.
---

# Pylontech Battery Stack Analysis Skill

This skill analyzes Pylontech LiFePo4 (Lithium Iron Phosphate) battery stack telemetry using:
1. **Live diagnostics** queried directly from the battery console via the local **Pylontech MCP Server** (exposing tools like `raw_command` and `get_pwr_status`).
2. **Historical trends** collected via Prometheus exporter and retrieved via the **Grafana MCP Server**.
3. **Static log files** or raw serial console log dumps.

Use this skill when:
- Querying live metrics or logs directly from the Pylontech battery stack using the Pylontech MCP server.
- Analyzing serial console log outputs.
- Querying Prometheus/Grafana datasets for historical trends.

## Help Section

Run this skill's analysis helper using:
```bash
python scripts/analyze_pylontech.py <console_log_file>
```

Commands available to all Agents:
- `help`: Read this file for instructions, formulas, Slovak terminology mapping, and PromQL queries.
- `analyze`: Parse serial output files (`pwr`, `stat`, `info`, `bat`, `soh`) and cross-verify with Prometheus ranges.

---

## 1. Key Mathematical Formulas & Unit Conversion

From Pylontech `stat` console commands:
- **Pwr Coulomb** is stored in **milli-coulombs (mC)**:
  $$\text{Capacity (Ah)} = \frac{\text{Pwr Coulomb}}{3\,600\,000}$$
  $$\text{Capacity (mAh)} = \frac{\text{Pwr Coulomb}}{3\,600}$$
- **Dsg Cap** is stored in **milliampere-hours (mAh)**:
  $$\text{Discharged Capacity (Ah)} = \frac{\text{Dsg Cap}}{1\,000}$$
- **Cycles Calculation Verification:**
  $$\text{Avg Ah per cycle} = \frac{\text{Dsg Cap (mAh)}}{\text{Cycle Times} \times 1\,000}$$

---

## 2. Slovak Terminology Mapping

When writing Slovak copies of the report (`_SK.md`), adhere to the following terminology:
- **Cell spread:** Článkový spread (napäťové alebo coulombovské rozpätie článkov)
- **State of Charge (SoC):** Stav nabitia (SoC)
- **State of Health (SoH):** Stav zdravia (SOH)
- **Current Sharing / Participation:** Zdieľanie prúdu / Účasť na prúde
- **Resets / Shutdowns:** Počty resetov / Počty vypnutí (shutdownov)
- **Low Voltage Count:** Počet podpätí (low-voltage udalostí)
- **Thermal stratification:** Vertikálna teplotná stratifikácia v racku
- **Watch cells:** Články na sledovanie

---

## 3. Physical Context & Ambient Correlation Rules

1. **Ambient Temperature Correlation:**
   - Always correlate module temperatures with the room sensor (`sensor.espresense_dielna_bme280_temperature` or similar).
   - If the correlation coefficient is **>0.90**, explicitly report that temperature swings are driven by ambient room fluctuations (weather), not battery self-heating.
2. **Rack Height Effect:**
   - Note the physical order of modules in the rack.
   - Module #1 (top) runs warmest (+4.3°C average room delta) due to rising warm air.
   - Module #6 (bottom, 5 cm above ground) runs coolest (+2.8°C average room delta) due to cold air pooling.

---

## 4. PromQL Queries

### Per-module Coulomb Percent (SoC)
```promql
label_replace(
  homeassistant_sensor_battery_percent{job="hass",entity=~"sensor.pylontech_battery_[1-6]_coulomb_percent"},
  "battery","$1","entity","sensor\\.pylontech_battery_(\\d+)_coulomb_percent"
)
```

### Cell Voltage Spread
```promql
max by (battery) (
  label_replace(homeassistant_sensor_voltage_v{job="hass",entity=~"sensor.pylontech_battery_[1-6]_high_voltage"},
  "battery","$1","entity","sensor\\.pylontech_battery_(\\d+)_high_voltage")
)
- on (battery)
max by (battery) (
  label_replace(homeassistant_sensor_voltage_v{job="hass",entity=~"sensor.pylontech_battery_[1-6]_low_voltage"},
  "battery","$1","entity","sensor\\.pylontech_battery_(\\d+)_low_voltage")
)
```

### Cumulative Fault Event Deltas (21d)
```promql
sum by (entity) (
  clamp_min(
    max_over_time(homeassistant_sensor_state{job="hass",entity=~"sensor.pylontech_battery_[1-6]_(battery_over_voltage_times|battery_under_voltage_times|power_over_voltage_times|power_under_voltage_times|charge_over_temperature_times|discharge_over_temperature_times|charge_over_current_times|discharge_over_current_times|bmic_error_times|short_circuit_times|life_alarm_times)"}[21d])
    -
    min_over_time(homeassistant_sensor_state{job="hass",entity=~"sensor.pylontech_battery_[1-6]_(battery_over_voltage_times|battery_under_voltage_times|power_over_voltage_times|power_under_voltage_times|charge_over_temperature_times|discharge_over_temperature_times|charge_over_current_times|discharge_over_current_times|bmic_error_times|short_circuit_times|life_alarm_times)"}[21d]),
    0
  )
)
```
