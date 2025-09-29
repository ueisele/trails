# Trail Routing System Architecture Guide

## Executive Summary

This guide provides comprehensive architecture recommendations for building a custom trail routing system with snap-to-trail navigation, elevation awareness, and support for Norwegian Kartverket data sources.

### Key Decisions
- **Frontend**: React + TypeScript + Mapbox GL JS
- **Backend**: Go + Fiber + PostGIS (primary), Python for GIS operations
- **Database**: PostgreSQL with PostGIS extension
- **Caching**: Redis for distributed cache, in-memory for hot paths
- **Deployment**: Docker containers with Kubernetes orchestration

## System Overview

```mermaid
graph TB
    subgraph "Frontend"
        UI[React + TypeScript]
        MAP[Mapbox GL JS]
        PWA[PWA Service Worker]
    end

    subgraph "API Gateway"
        GW[Kong/Traefik]
    end

    subgraph "Backend Services"
        ROUTE[Go Routing Service]
        ELEV[Python Elevation Service]
        TILE[Tile Server]
        AUTH[Auth Service]
    end

    subgraph "Data Layer"
        PG[(PostGIS)]
        REDIS[(Redis Cache)]
        S3[Object Storage]
        DEM[DEM Files]
    end

    UI --> MAP
    MAP --> GW
    GW --> ROUTE
    GW --> ELEV
    GW --> TILE
    ROUTE --> PG
    ROUTE --> REDIS
    ELEV --> DEM
    TILE --> S3
```

## Frontend Architecture

### Technology Stack

#### Primary Recommendation: React + TypeScript + Mapbox GL JS

```typescript
// Tech stack
{
  "core": {
    "framework": "React 18",
    "language": "TypeScript 5",
    "bundler": "Vite",
    "styling": "Tailwind CSS"
  },
  "mapping": {
    "engine": "Mapbox GL JS",  // or MapLibre GL for open source
    "draw": "@mapbox/mapbox-gl-draw",
    "geocoding": "@mapbox/mapbox-gl-geocoder"
  },
  "state": {
    "client": "TanStack Query",
    "local": "Zustand"
  },
  "ui": {
    "components": "Radix UI",
    "charts": "Recharts",
    "forms": "React Hook Form"
  },
  "utilities": {
    "spatial": "@turf/turf",
    "gpx": "gpxparser",
    "date": "date-fns"
  }
}
```

#### Component Architecture

```typescript
// src/components/TrailRouter/TrailRouter.tsx
import { useState, useCallback } from 'react';
import Map, { Source, Layer } from 'react-map-gl';
import { useQuery, useMutation } from '@tanstack/react-query';

interface TrailRouterProps {
  initialBounds: BoundingBox;
  trailData: FeatureCollection;
}

export const TrailRouter: React.FC<TrailRouterProps> = ({
  initialBounds,
  trailData
}) => {
  const [waypoints, setWaypoints] = useState<LngLat[]>([]);

  // Fetch trails in viewport
  const { data: trails } = useQuery({
    queryKey: ['trails', viewport],
    queryFn: () => fetchTrails(viewport),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Calculate route mutation
  const routeMutation = useMutation({
    mutationFn: calculateRoute,
    onSuccess: (route) => {
      displayRoute(route);
      generateElevationProfile(route);
    }
  });

  return (
    <div className="flex h-screen">
      <div className="flex-1">
        <Map
          mapboxAccessToken={MAPBOX_TOKEN}
          initialViewState={initialBounds}
          mapStyle="mapbox://styles/mapbox/outdoors-v12"
          terrain={{ source: 'mapbox-dem', exaggeration: 1.5 }}
        >
          <KartverketOverlay />
          <TrailLayer data={trails} />
          <RouteLayer data={routeMutation.data} />
          <WaypointMarkers points={waypoints} />
        </Map>
      </div>
      <Sidebar>
        <RouteControls onCalculate={routeMutation.mutate} />
        <ElevationProfile data={routeMutation.data?.elevation} />
        <RouteStats stats={routeMutation.data?.statistics} />
      </Sidebar>
    </div>
  );
};
```

### Alternative Frontend Stacks

| Stack | Pros | Cons | Best For |
|-------|------|------|----------|
| **Vue 3 + MapLibre GL** | Simpler, 100% open source, smaller bundle | Smaller ecosystem | Open source projects |
| **SolidJS + MapGL** | Best performance, tiny bundle | Small community | Performance-critical apps |
| **Svelte + Mapbox** | No virtual DOM, built-in stores | Less mature | Lightweight PWAs |
| **Angular + Leaflet** | Enterprise-ready, TypeScript-first | Heavy, steeper learning | Enterprise applications |

### Norwegian-Specific Frontend Configuration

```typescript
// src/config/norwegian-maps.ts
export const NORWEGIAN_MAP_CONFIG = {
  // Kartverket basemaps
  basemaps: {
    topo: {
      type: 'raster',
      tiles: ['https://cache.kartverket.no/topo4/v1/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© Kartverket'
    },
    aerial: {
      type: 'raster',
      tiles: ['https://waapi.webatlas.no/maptiles/tiles/webatlas-orto-newup/wa_grid/{z}/{x}/{y}.jpeg'],
      tileSize: 256
    }
  },

  // Trail difficulty styling
  trailStyles: {
    'T1': { color: '#00ff00', width: 3, opacity: 0.8 },
    'T2': { color: '#ffff00', width: 3, opacity: 0.8 },
    'T3': { color: '#ff8800', width: 4, opacity: 0.8 },
    'T4': { color: '#ff0000', width: 4, opacity: 0.9 },
    'T5': { color: '#800000', width: 5, opacity: 0.9 },
    'T6': { color: '#400000', width: 5, opacity: 1.0 }
  },

  // Coordinate systems
  projection: 'EPSG:4326',  // WGS84 for web
  displayProjection: 'EPSG:25833',  // UTM 33N for display

  // Localization
  locale: 'nb-NO',
  units: 'metric'
};
```

## Backend Architecture

### Technology Stack Comparison

| Language | Performance | GIS Libraries | Dev Speed | Deployment | Best For |
|----------|------------|---------------|-----------|------------|----------|
| **Go** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | APIs, routing algorithms |
| **Python** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | GIS processing, ML |
| **Rust** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | Maximum performance |
| **Node.js** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Full-stack JavaScript |
| **Java** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | Enterprise, GraphHopper |

### Primary Backend: Go + Fiber

```go
// cmd/api/main.go
package main

import (
    "context"
    "time"

    "github.com/gofiber/fiber/v2"
    "github.com/gofiber/fiber/v2/middleware/cors"
    "github.com/gofiber/fiber/v2/middleware/compress"
    "github.com/gofiber/fiber/v2/middleware/cache"
    "github.com/jackc/pgx/v5/pgxpool"
    "github.com/redis/go-redis/v9"
)

type Server struct {
    app    *fiber.App
    db     *pgxpool.Pool
    cache  *redis.Client
    router *TrailRouter
}

func NewServer() (*Server, error) {
    // Database connection
    db, err := pgxpool.New(context.Background(), os.Getenv("DATABASE_URL"))
    if err != nil {
        return nil, err
    }

    // Redis cache
    cache := redis.NewClient(&redis.Options{
        Addr: os.Getenv("REDIS_URL"),
        DB:   0,
    })

    // Initialize routing engine
    router := NewTrailRouter(db, cache)

    // Setup Fiber
    app := fiber.New(fiber.Config{
        BodyLimit: 10 * 1024 * 1024, // 10MB
        Concurrency: 256 * 1024,      // Max concurrent connections
    })

    // Middleware
    app.Use(cors.New())
    app.Use(compress.New())
    app.Use(cache.New(cache.Config{
        Expiration: 1 * time.Hour,
        CacheControl: true,
    }))

    return &Server{app, db, cache, router}, nil
}

func (s *Server) setupRoutes() {
    api := s.app.Group("/api")

    // Routing endpoints
    api.Post("/route", s.calculateRoute)
    api.Get("/route/:id", s.getRoute)
    api.Post("/route/multi", s.calculateMultiDayRoute)

    // Trail data
    api.Get("/trails", s.getTrails)
    api.Get("/trails/:id", s.getTrailDetails)
    api.Get("/trails/bbox/:bbox", s.getTrailsInBounds)

    // Elevation
    api.Post("/elevation/profile", s.getElevationProfile)
    api.Get("/elevation/point/:lat/:lon", s.getElevationAtPoint)

    // Export
    api.Post("/export/gpx", s.exportGPX)
    api.Post("/export/kml", s.exportKML)
}
```

### Routing Service Implementation

```go
// internal/routing/router.go
package routing

import (
    "container/heap"
    "math"

    "github.com/paulmach/orb"
    "github.com/tidwall/rtree"
)

type TrailRouter struct {
    graph    *Graph
    index    *rtree.RTree
    elevation *ElevationService
    cache    *Cache
}

type RoutingOptions struct {
    Profile           string
    AvoidDifficulties []string
    PreferMarkedTrails bool
    MaxElevationGain  float64
    ConsiderWeather   bool
}

func (r *TrailRouter) CalculateRoute(
    start, end orb.Point,
    options RoutingOptions,
) (*Route, error) {
    // Check cache
    cacheKey := generateCacheKey(start, end, options)
    if cached := r.cache.Get(cacheKey); cached != nil {
        return cached.(*Route), nil
    }

    // Snap to network
    startNode := r.snapToNetwork(start)
    endNode := r.snapToNetwork(end)

    // A* pathfinding
    path := r.astar(startNode, endNode, options)

    // Build route with metadata
    route := r.buildRoute(path)

    // Add elevation profile
    route.Elevation = r.elevation.GetProfile(route.Geometry)

    // Cache result
    r.cache.Set(cacheKey, route, 1*time.Hour)

    return route, nil
}

func (r *TrailRouter) astar(start, end *Node, options RoutingOptions) []*Node {
    openSet := &PriorityQueue{}
    heap.Init(openSet)

    cameFrom := make(map[*Node]*Node)
    gScore := make(map[*Node]float64)
    fScore := make(map[*Node]float64)

    gScore[start] = 0
    fScore[start] = r.heuristic(start, end)
    heap.Push(openSet, &Item{node: start, priority: fScore[start]})

    for openSet.Len() > 0 {
        current := heap.Pop(openSet).(*Item).node

        if current == end {
            return r.reconstructPath(cameFrom, current)
        }

        for _, edge := range current.edges {
            neighbor := edge.target

            // Calculate cost based on options
            cost := r.calculateCost(edge, options)
            tentativeGScore := gScore[current] + cost

            if existingScore, exists := gScore[neighbor]; !exists || tentativeGScore < existingScore {
                cameFrom[neighbor] = current
                gScore[neighbor] = tentativeGScore
                fScore[neighbor] = tentativeGScore + r.heuristic(neighbor, end)
                heap.Push(openSet, &Item{node: neighbor, priority: fScore[neighbor]})
            }
        }
    }

    return nil // No path found
}

func (r *TrailRouter) calculateCost(edge *Edge, options RoutingOptions) float64 {
    baseCost := edge.length

    // Difficulty penalty
    difficultyMultiplier := 1.0
    switch edge.difficulty {
    case "T1": difficultyMultiplier = 1.0
    case "T2": difficultyMultiplier = 1.2
    case "T3": difficultyMultiplier = 1.5
    case "T4": difficultyMultiplier = 2.0
    case "T5": difficultyMultiplier = 3.0
    case "T6": difficultyMultiplier = 5.0
    }

    // Elevation penalty
    elevationMultiplier := 1.0
    if edge.elevationGain > 0 {
        elevationMultiplier = 1.0 + (edge.elevationGain / 100.0) * 0.5
    }

    // Surface penalty
    surfaceMultiplier := 1.0
    switch edge.surface {
    case "paved": surfaceMultiplier = 0.9
    case "gravel": surfaceMultiplier = 1.0
    case "dirt": surfaceMultiplier = 1.1
    case "rock": surfaceMultiplier = 1.5
    case "scree": surfaceMultiplier = 2.0
    }

    // Marked trail bonus
    markedBonus := 1.0
    if options.PreferMarkedTrails && edge.marked {
        markedBonus = 0.8
    }

    return baseCost * difficultyMultiplier * elevationMultiplier * surfaceMultiplier * markedBonus
}
```

### Supporting Python Service for GIS Operations

```python
# services/elevation/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Tuple
import rasterio
import numpy as np
from shapely.geometry import LineString, Point
import geopandas as gpd

app = FastAPI(title="Elevation Service")

class ElevationService:
    def __init__(self, dem_path: str):
        self.dem = rasterio.open(dem_path)
        self.transform = self.dem.transform

    def get_elevation(self, lon: float, lat: float) -> float:
        """Get elevation at a single point"""
        row, col = ~self.transform * (lon, lat)

        if 0 <= row < self.dem.height and 0 <= col < self.dem.width:
            elevation = self.dem.read(1)[int(row), int(col)]
            return float(elevation)
        return None

    def get_profile(self, coordinates: List[Tuple[float, float]]) -> dict:
        """Get elevation profile along a route"""
        elevations = []
        distances = [0]
        total_distance = 0

        for i, (lon, lat) in enumerate(coordinates):
            elevation = self.get_elevation(lon, lat)
            elevations.append(elevation)

            if i > 0:
                prev_lon, prev_lat = coordinates[i-1]
                distance = self._calculate_distance(
                    prev_lon, prev_lat, lon, lat
                )
                total_distance += distance
                distances.append(total_distance)

        # Calculate statistics
        gain = sum(max(0, elevations[i] - elevations[i-1])
                  for i in range(1, len(elevations)))
        loss = sum(max(0, elevations[i-1] - elevations[i])
                  for i in range(1, len(elevations)))

        return {
            'elevations': elevations,
            'distances': distances,
            'total_distance': total_distance,
            'elevation_gain': gain,
            'elevation_loss': loss,
            'min_elevation': min(elevations),
            'max_elevation': max(elevations)
        }

# Initialize with Kartverket DEM
elevation_service = ElevationService('/data/kartverket_10m.tif')

@app.post("/elevation/profile")
async def get_elevation_profile(coordinates: List[List[float]]):
    """Get elevation profile for a route"""
    try:
        profile = elevation_service.get_profile(coordinates)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/elevation/point/{lat}/{lon}")
async def get_elevation_at_point(lat: float, lon: float):
    """Get elevation at a specific point"""
    elevation = elevation_service.get_elevation(lon, lat)
    if elevation is None:
        raise HTTPException(status_code=404, detail="Point outside DEM coverage")
    return {'elevation': elevation, 'coordinates': [lon, lat]}
```

## Database Architecture

### PostgreSQL with PostGIS Schema

```sql
-- Main trail data
CREATE TABLE trails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    name TEXT,
    name_no TEXT,
    trail_number TEXT,
    difficulty VARCHAR(10) CHECK (difficulty IN ('T1','T2','T3','T4','T5','T6')),
    surface VARCHAR(50),
    operator TEXT,
    marked BOOLEAN DEFAULT false,
    seasonal BOOLEAN DEFAULT false,
    length_m FLOAT GENERATED ALWAYS AS (ST_Length(geom::geography)) STORED,
    bbox GEOMETRY(POLYGON, 4326) GENERATED ALWAYS AS (ST_Envelope(geom)) STORED,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Routing network
CREATE TABLE trail_network (
    id SERIAL PRIMARY KEY,
    source INTEGER NOT NULL,
    target INTEGER NOT NULL,
    cost FLOAT NOT NULL,
    reverse_cost FLOAT NOT NULL,
    trail_id UUID REFERENCES trails(id),
    difficulty VARCHAR(10),
    surface VARCHAR(50),
    elevation_gain FLOAT,
    elevation_loss FLOAT,
    geom GEOMETRY(LINESTRING, 4326) NOT NULL
);

-- Network nodes
CREATE TABLE trail_nodes (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(POINT, 4326) NOT NULL,
    elevation FLOAT,
    type VARCHAR(50), -- trailhead, junction, peak, hut
    name TEXT,
    facilities JSONB
);

-- Cached routes
CREATE TABLE cached_routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    start_point GEOMETRY(POINT, 4326) NOT NULL,
    end_point GEOMETRY(POINT, 4326) NOT NULL,
    waypoints GEOMETRY(MULTIPOINT, 4326),
    profile VARCHAR(50) NOT NULL,
    options JSONB,
    route_geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    distance_m FLOAT NOT NULL,
    duration_min INTEGER,
    elevation_gain FLOAT,
    elevation_loss FLOAT,
    difficulty_max VARCHAR(10),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    accessed_at TIMESTAMPTZ DEFAULT NOW(),
    access_count INTEGER DEFAULT 1
);

-- User saved routes
CREATE TABLE user_routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    route_geom GEOMETRY(LINESTRING, 4326) NOT NULL,
    waypoints JSONB,
    statistics JSONB,
    tags TEXT[],
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_trails_geom ON trails USING GIST (geom);
CREATE INDEX idx_trails_bbox ON trails USING GIST (bbox);
CREATE INDEX idx_trails_difficulty ON trails (difficulty);
CREATE INDEX idx_trails_operator ON trails (operator);
CREATE INDEX idx_trail_network_source ON trail_network (source);
CREATE INDEX idx_trail_network_target ON trail_network (target);
CREATE INDEX idx_trail_network_geom ON trail_network USING GIST (geom);
CREATE INDEX idx_trail_nodes_geom ON trail_nodes USING GIST (geom);
CREATE INDEX idx_cached_routes_points ON cached_routes USING GIST (start_point, end_point);
CREATE INDEX idx_cached_routes_created ON cached_routes (created_at);

-- Clustering for spatial queries
CLUSTER trails USING idx_trails_geom;
CLUSTER trail_network USING idx_trail_network_geom;
```

## Caching Strategy

### Multi-Level Cache Architecture

```go
// internal/cache/multilevel.go
package cache

import (
    "context"
    "encoding/json"
    "time"

    "github.com/dgraph-io/ristretto"
    "github.com/redis/go-redis/v9"
    "github.com/jackc/pgx/v5/pgxpool"
)

type MultiLevelCache struct {
    l1 *ristretto.Cache  // In-memory LRU (microseconds)
    l2 *redis.Client     // Redis distributed (milliseconds)
    l3 *pgxpool.Pool     // PostgreSQL persistent (10s ms)
}

func NewMultiLevelCache(redis *redis.Client, db *pgxpool.Pool) (*MultiLevelCache, error) {
    // L1: In-memory cache
    l1, err := ristretto.NewCache(&ristretto.Config{
        NumCounters: 1e7,     // 10 million
        MaxCost:     1 << 30, // 1GB
        BufferItems: 64,
    })
    if err != nil {
        return nil, err
    }

    return &MultiLevelCache{
        l1: l1,
        l2: redis,
        l3: db,
    }, nil
}

func (c *MultiLevelCache) Get(ctx context.Context, key string) (interface{}, error) {
    // L1: Memory cache
    if value, found := c.l1.Get(key); found {
        return value, nil
    }

    // L2: Redis cache
    data, err := c.l2.Get(ctx, key).Bytes()
    if err == nil {
        var value interface{}
        if err := json.Unmarshal(data, &value); err == nil {
            // Promote to L1
            c.l1.Set(key, value, 1)
            return value, nil
        }
    }

    // L3: Database cache
    var routeData []byte
    err = c.l3.QueryRow(ctx, `
        UPDATE cached_routes
        SET accessed_at = NOW(), access_count = access_count + 1
        WHERE id = $1
        RETURNING route_data
    `, key).Scan(&routeData)

    if err == nil {
        var value interface{}
        if err := json.Unmarshal(routeData, &value); err == nil {
            // Promote to L1 and L2
            c.l1.Set(key, value, 1)
            c.l2.Set(ctx, key, routeData, 1*time.Hour)
            return value, nil
        }
    }

    return nil, ErrCacheMiss
}

func (c *MultiLevelCache) Set(ctx context.Context, key string, value interface{}, ttl time.Duration) error {
    data, err := json.Marshal(value)
    if err != nil {
        return err
    }

    // Write through all levels
    c.l1.Set(key, value, 1)
    c.l2.Set(ctx, key, data, ttl)

    // Async write to database
    go func() {
        ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
        defer cancel()

        _, _ = c.l3.Exec(ctx, `
            INSERT INTO cached_routes (id, route_data, ttl)
            VALUES ($1, $2, $3)
            ON CONFLICT (id) DO UPDATE
            SET route_data = EXCLUDED.route_data,
                updated_at = NOW()
        `, key, data, ttl)
    }()

    return nil
}
```

## Deployment Architecture

### Docker Compose Development

```yaml
# docker-compose.yml
version: '3.9'

services:
  # API Gateway
  gateway:
    image: traefik:v3.0
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./traefik.yml:/etc/traefik/traefik.yml
      - ./certs:/certs
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.dashboard.rule=Host(`traefik.localhost`)"

  # Main routing API (Go)
  routing-api:
    build:
      context: ./services/routing
      dockerfile: Dockerfile
    environment:
      - DATABASE_URL=postgresql://postgres:password@postgres:5432/trails
      - REDIS_URL=redis:6379
      - ELEVATION_SERVICE_URL=http://elevation-api:8000
    depends_on:
      - postgres
      - redis
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.localhost`)"
      - "traefik.http.services.api.loadbalancer.server.port=8080"
    deploy:
      replicas: 3

  # Elevation service (Python)
  elevation-api:
    build:
      context: ./services/elevation
      dockerfile: Dockerfile
    volumes:
      - ./data/dem:/data/dem:ro
    environment:
      - DEM_PATH=/data/dem/kartverket_10m.tif
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.elevation.rule=Host(`api.localhost`) && PathPrefix(`/elevation`)"

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - VITE_API_URL=http://api.localhost
      - VITE_MAPBOX_TOKEN=${MAPBOX_TOKEN}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`app.localhost`)"

  # Database
  postgres:
    image: postgis/postgis:15-3.3
    environment:
      - POSTGRES_DB=trails
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  # Cache
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"

  # Tile server
  tileserver:
    image: maptiler/tileserver-gl:latest
    volumes:
      - ./data/tiles:/data
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.tiles.rule=Host(`tiles.localhost`)"

volumes:
  pgdata:
  redisdata:
```

### Kubernetes Production Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: routing-api
  namespace: trail-routing
spec:
  replicas: 3
  selector:
    matchLabels:
      app: routing-api
  template:
    metadata:
      labels:
        app: routing-api
    spec:
      containers:
      - name: api
        image: trail-routing/api:latest
        ports:
        - containerPort: 8080
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: REDIS_URL
          value: redis-service:6379
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: routing-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: routing-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## API Design

### RESTful API Specification

```yaml
# openapi.yaml
openapi: 3.0.3
info:
  title: Trail Routing API
  description: Norwegian trail routing with elevation awareness
  version: 1.0.0

servers:
  - url: https://api.trails.no/v1

paths:
  /route:
    post:
      summary: Calculate route between waypoints
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - waypoints
                - profile
              properties:
                waypoints:
                  type: array
                  minItems: 2
                  items:
                    type: object
                    properties:
                      lat:
                        type: number
                      lon:
                        type: number
                profile:
                  type: string
                  enum: [hiking, skiing, biking, running]
                preferences:
                  type: object
                  properties:
                    avoid_difficulties:
                      type: array
                      items:
                        type: string
                        enum: [T4, T5, T6]
                    prefer_marked_trails:
                      type: boolean
                    max_elevation_gain:
                      type: number
                    max_distance:
                      type: number
                    consider_weather:
                      type: boolean
      responses:
        '200':
          description: Successful route calculation
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Route'
        '400':
          description: Invalid request
        '404':
          description: No route found
        '500':
          description: Server error

  /trails:
    get:
      summary: Get trails in bounding box
      parameters:
        - in: query
          name: bbox
          required: true
          schema:
            type: string
          description: Bounding box (west,south,east,north)
        - in: query
          name: difficulty
          schema:
            type: array
            items:
              type: string
        - in: query
          name: marked_only
          schema:
            type: boolean
      responses:
        '200':
          description: Trail features
          content:
            application/geo+json:
              schema:
                $ref: '#/components/schemas/FeatureCollection'

  /elevation/profile:
    post:
      summary: Get elevation profile for coordinates
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                coordinates:
                  type: array
                  items:
                    type: array
                    items:
                      type: number
      responses:
        '200':
          description: Elevation profile
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ElevationProfile'

components:
  schemas:
    Route:
      type: object
      properties:
        id:
          type: string
          format: uuid
        geometry:
          $ref: '#/components/schemas/LineString'
        distance:
          type: number
          description: Distance in meters
        duration:
          type: number
          description: Duration in minutes
        elevation_gain:
          type: number
        elevation_loss:
          type: number
        difficulty_max:
          type: string
        segments:
          type: array
          items:
            $ref: '#/components/schemas/RouteSegment'
        elevation_profile:
          $ref: '#/components/schemas/ElevationProfile'

    RouteSegment:
      type: object
      properties:
        trail_id:
          type: string
        trail_name:
          type: string
        difficulty:
          type: string
        surface:
          type: string
        distance:
          type: number
        elevation_gain:
          type: number

    ElevationProfile:
      type: object
      properties:
        elevations:
          type: array
          items:
            type: number
        distances:
          type: array
          items:
            type: number
        total_distance:
          type: number
        elevation_gain:
          type: number
        elevation_loss:
          type: number
        min_elevation:
          type: number
        max_elevation:
          type: number
```

## Performance Optimization

### Backend Optimizations

```go
// Spatial indexing with S2
import "github.com/golang/geo/s2"

type S2Index struct {
    index map[s2.CellID][]*Trail
    level int
}

func (idx *S2Index) Add(trail *Trail) {
    for _, point := range trail.Points {
        cellID := s2.CellFromLatLng(s2.LatLngFromDegrees(point.Lat, point.Lon)).ID()
        idx.index[cellID.Parent(idx.level)] = append(
            idx.index[cellID.Parent(idx.level)],
            trail,
        )
    }
}

func (idx *S2Index) Query(bounds s2.Rect) []*Trail {
    covering := s2.RegionCoverer{MaxLevel: idx.level}.Covering(bounds)
    results := make([]*Trail, 0)
    seen := make(map[string]bool)

    for _, cellID := range covering {
        for _, trail := range idx.index[cellID] {
            if !seen[trail.ID] {
                results = append(results, trail)
                seen[trail.ID] = true
            }
        }
    }
    return results
}
```

### Frontend Optimizations

```typescript
// Virtual scrolling for large trail lists
import { VirtualList } from '@tanstack/react-virtual';

// Web Workers for heavy computations
const routingWorker = new Worker('/workers/routing.worker.js');

// Lazy loading with React.lazy and Suspense
const ElevationProfile = lazy(() => import('./ElevationProfile'));

// Memoization for expensive calculations
const memoizedRouteStats = useMemo(
  () => calculateRouteStatistics(route),
  [route]
);

// Debounced map updates
const debouncedMapUpdate = useMemo(
  () => debounce(updateMapView, 300),
  []
);
```

## Monitoring and Observability

### Metrics Stack

```yaml
# Prometheus + Grafana + Jaeger
services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-data:/var/lib/grafana
      - ./dashboards:/etc/grafana/provisioning/dashboards

  jaeger:
    image: jaegertracing/all-in-one:latest
    environment:
      - COLLECTOR_ZIPKIN_HOST_PORT=:9411
    ports:
      - "16686:16686"
      - "14268:14268"
```

### Application Metrics

```go
// Prometheus metrics
var (
    routeCalculationDuration = promauto.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "route_calculation_duration_seconds",
            Help: "Time taken to calculate a route",
        },
        []string{"profile", "distance_category"},
    )

    cacheHitRate = promauto.NewCounterVec(
        prometheus.CounterOpts{
            Name: "cache_hits_total",
            Help: "Number of cache hits",
        },
        []string{"cache_level"},
    )
)
```

## Security Considerations

### API Security

```go
// Rate limiting
import "github.com/ulule/limiter/v3"

rateLimiter := limiter.New(
    memory.NewStore(),
    limiter.Rate{Period: 1 * time.Minute, Limit: 60},
)

// JWT authentication
import "github.com/golang-jwt/jwt/v5"

func validateToken(tokenString string) (*Claims, error) {
    token, err := jwt.ParseWithClaims(
        tokenString,
        &Claims{},
        func(token *jwt.Token) (interface{}, error) {
            return jwtKey, nil
        },
    )
    // ...
}

// Input validation
type RouteRequest struct {
    Waypoints []Point `json:"waypoints" validate:"required,min=2,max=25"`
    Profile   string  `json:"profile" validate:"required,oneof=hiking skiing biking"`
}
```

## Testing Strategy

### Unit Testing

```go
// router_test.go
func TestRouteCalculation(t *testing.T) {
    router := NewTestRouter()

    tests := []struct {
        name     string
        start    orb.Point
        end      orb.Point
        options  RoutingOptions
        wantDist float64
        wantErr  bool
    }{
        {
            name:  "simple route",
            start: orb.Point{10.7522, 59.9139},
            end:   orb.Point{10.7389, 59.9275},
            options: RoutingOptions{Profile: "hiking"},
            wantDist: 2150.0,
            wantErr: false,
        },
        // More test cases...
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            route, err := router.CalculateRoute(tt.start, tt.end, tt.options)
            if (err != nil) != tt.wantErr {
                t.Errorf("unexpected error: %v", err)
            }
            if route != nil && math.Abs(route.Distance-tt.wantDist) > 10 {
                t.Errorf("distance = %v, want %v", route.Distance, tt.wantDist)
            }
        })
    }
}
```

### Integration Testing

```typescript
// frontend/tests/integration/routing.test.ts
describe('Trail Routing Integration', () => {
  it('should calculate route between two points', async () => {
    const response = await api.calculateRoute({
      waypoints: [
        { lat: 59.9139, lon: 10.7522 },
        { lat: 59.9275, lon: 10.7389 }
      ],
      profile: 'hiking'
    });

    expect(response.status).toBe(200);
    expect(response.data).toHaveProperty('geometry');
    expect(response.data.distance).toBeGreaterThan(0);
    expect(response.data.elevation_profile).toBeDefined();
  });
});
```

## Cost Analysis

### Infrastructure Costs (Monthly)

| Component | Development | Production | High Availability |
|-----------|------------|------------|-------------------|
| **Compute** |
| API Servers | $20 (1x small) | $200 (3x medium) | $600 (6x large) |
| Database | $20 (small) | $100 (medium) | $400 (cluster) |
| Cache | $10 (512MB) | $50 (4GB) | $150 (cluster) |
| **Storage** |
| Object Storage | $5 (50GB) | $20 (200GB) | $50 (500GB) |
| DEM Data | $10 (100GB) | $10 (100GB) | $30 (replicated) |
| **Network** |
| CDN | $0 | $50 | $200 |
| Load Balancer | $0 | $20 | $40 |
| **Total** | **$65** | **$450** | **$1470** |

### Development Time Estimates

| Component | Junior Dev | Senior Dev | Team of 3 |
|-----------|-----------|-----------|-----------|
| Backend API | 3 months | 6 weeks | 3 weeks |
| Frontend | 2 months | 4 weeks | 2 weeks |
| Database | 1 month | 2 weeks | 1 week |
| DevOps | 1 month | 2 weeks | 1 week |
| Testing | 1 month | 2 weeks | 1 week |
| **Total** | **8 months** | **16 weeks** | **8 weeks** |

## Conclusion

### Technology Recommendations Summary

1. **Frontend**: React + TypeScript + Mapbox GL JS
   - Best ecosystem and mapping capabilities
   - Strong typing for GIS data
   - Excellent developer experience

2. **Backend**: Go (primary) + Python (GIS operations)
   - Go for performance-critical routing
   - Python for complex GIS processing
   - Microservices architecture for scalability

3. **Database**: PostgreSQL with PostGIS
   - Industry standard for spatial data
   - Excellent routing support with pgRouting
   - Mature and reliable

4. **Caching**: Redis + In-memory
   - Multi-level caching for optimal performance
   - Distributed caching for scalability

5. **Deployment**: Docker + Kubernetes
   - Container orchestration for production
   - Easy scaling and management
   - Cloud-agnostic

### Decision Tree

```
Need custom trail routing?
├─ Yes
│  ├─ High performance critical?
│  │  ├─ Yes → Go backend + React frontend
│  │  └─ No → Python backend + Vue frontend
│  └─ Complex GIS operations?
│     ├─ Yes → Add Python microservice
│     └─ No → Go only
└─ No → Use existing tools (GraphHopper, BRouter)
```

This architecture provides a solid foundation for building a production-ready trail routing system with Norwegian data support and international extensibility.
