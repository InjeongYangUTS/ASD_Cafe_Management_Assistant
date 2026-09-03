# Inventory Agent Prompt Assets

## Context

The agent receives inventory records from inventory.db. Only LOW and
OUT OF STOCK items are included.

Each record contains:

- Item ID
- Item name
- Current quantity
- Unit
- Minimum stock
- Shortage
- Authoritative status

## Plan Prompt

Identifies critical stock problems and determines analysis priorities.

## Act Prompt

Separates OUT OF STOCK and LOW items and analyses shortage values.

## Observe Prompt

Compares the Act result with the original database context and identifies
incorrect statuses, quantities, missing items, and unsupported claims.

## Adapt Prompt

Uses the original context and Observe result to produce a corrected,
numbered recommendation.

## Context-management rules

- Database values are authoritative.
- OUT OF STOCK has higher priority than LOW.
- The model must not invent items or quantities.
- Status values must not be reinterpreted.
- The final response must be concise and practical.