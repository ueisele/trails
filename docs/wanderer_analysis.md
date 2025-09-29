# Wanderer.fr Analysis for Trail Routing Requirements

## Overview

Wanderer is a **self-hosted trail database** focused on managing and sharing GPX tracks. After analyzing the project, it does **NOT meet your requirements** for snap-to-trail routing with custom overlays.

## What Wanderer Is

- **Purpose**: Personal trail catalog and GPX track management
- **Tech Stack**: Svelte (frontend), Go (backend), PocketBase (database)
- **Open Source**: Yes, available at https://github.com/Flomp/wanderer
- **Self-Hosted**: Yes, runs via Docker

## Analysis Against Your Requirements

### ❌ **Snap-to-Trail Routing**
- **Status**: NOT SUPPORTED
- Wanderer is primarily a trail database, not a routing engine
- No routing algorithms (no GraphHopper, OSRM, pgRouting integration)
- Can only upload and display existing GPX tracks
- Cannot calculate routes between points
- No network topology or pathfinding capabilities

### ❌ **Custom Map Overlays**
- **Status**: NOT SUPPORTED
- No evidence of WMS/WMTS support
- No custom tile server configuration
- Cannot add Kartverket or other Norwegian map services
- Limited to default base maps only

### ❌ **Elevation Profiles**
- **Status**: UNCLEAR/LIMITED
- No clear elevation data integration
- No DEM support (including Kartverket 10m DEM)
- May display elevation if already in GPX files, but no analysis

### ❌ **Norwegian Trail Data**
- **Status**: NO SPECIFIC SUPPORT
- No integration with Geonorge/Kartverket
- No DNT trail data support
- Cannot import custom trail networks
- Only individual GPX file uploads

### ✅ **What It CAN Do**
- Store and organize GPX tracks
- Add metadata to trails (difficulty, tags, descriptions)
- Share trails with others (ActivityPub federation)
- Search and filter saved trails
- Display trails on a map
- Create lists/collections of trails

## Comparison with Your Needs

| Your Requirement | Wanderer Support | What You Actually Need |
|-----------------|------------------|------------------------|
| Snap-to-trail routing | ❌ No | GraphHopper, pgRouting, or BRouter |
| Route calculation | ❌ No | Routing engine with network topology |
| Custom map overlays | ❌ No | WMS/WMTS support for Kartverket |
| Norwegian elevation data | ❌ No | DEM integration capabilities |
| Trail network import | ❌ Limited | Bulk import of GeoJSON/OSM data |
| API for integration | ⚠️ Basic | Full routing API |
| Offline routing | ❌ No | BRouter or similar |

## Key Limitations for Your Use Case

1. **No Routing Engine**: Wanderer lacks any routing capabilities. It cannot:
   - Calculate optimal paths between points
   - Snap GPS coordinates to trail network
   - Consider trail difficulty or elevation in routing
   - Provide turn-by-turn navigation

2. **No Custom Data Sources**: Cannot integrate:
   - Norwegian topographic maps (Kartverket)
   - DNT trail network
   - AR5/AR50 land cover data
   - Custom elevation models

3. **Track Management Only**: Designed for:
   - Uploading completed hikes
   - Organizing personal trail collection
   - Sharing trails socially
   - Not for route planning

## Alternative Solutions That Meet Your Requirements

### Instead of Wanderer, Consider:

1. **GraphHopper** (Recommended)
   - ✅ Full snap-to-trail routing
   - ✅ Custom data import
   - ✅ Plugin system for Norwegian trails
   - ✅ API-first design

2. **Custom Solution**
   - Frontend: React + Mapbox GL JS
   - Backend: Go + PostGIS
   - Routing: GraphHopper or pgRouting
   - Maps: Kartverket WMS/WMTS

3. **BRouter + Custom UI**
   - ✅ Offline routing
   - ✅ Custom profiles
   - ✅ Low resource usage

## Verdict

**Wanderer is NOT suitable for your requirements.** It's a trail catalog system, not a routing platform. It lacks:
- Routing algorithms
- Snap-to-trail functionality
- Custom map overlay support
- Norwegian data integration capabilities

### What Wanderer IS Good For:
- Personal hiking diary
- Social trail sharing
- GPX file organization
- Simple trail visualization

### What You Need Instead:
A proper routing engine (GraphHopper, pgRouting, or BRouter) with:
- Network topology support
- Custom data import capabilities
- WMS/WMTS integration
- Elevation-aware routing
- API for programmatic access

## Recommendation

Skip Wanderer and focus on:
1. **GraphHopper** for production API with Norwegian data
2. **QGIS + pgRouting** for analysis and custom logic
3. **BRouter** for offline mobile use

These tools actually support snap-to-trail routing, custom overlays, and the flexibility you need for Norwegian trail planning.
