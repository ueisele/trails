# BRouter Customization Guide

## Overview

BRouter is **highly customizable** through its profile-based routing system. While it doesn't support plugins like GraphHopper, its profile language is incredibly powerful for routing logic customization.

## Customization Levels

### 1. Profile Customization (Primary Method) ⭐

BRouter's main customization happens through **routing profiles** - text files with a custom DSL (Domain Specific Language).

#### Profile Structure
```ini
# norwegian_hiking.brf
---context:global
assign validForFoot = true
assign validForBikes = false

# Cost parameters
assign downhillcost = 60
assign downhillcutoff = 1.5
assign uphillcost = 80
assign uphillcutoff = 1.5

# Custom variables
assign avoid_wetlands = true
assign prefer_dnt_trails = true
assign seasonal_mode = true  # Winter routing

---context:way
# Way-level routing decisions
assign turncost =
    if junction=roundabout then 20
    else if junction=crossing then 10
    else 0

# Trail classification costs
assign initialcost =
    switch trail_visibility=excellent 0
    switch trail_visibility=good 100
    switch trail_visibility=intermediate 300
    switch trail_visibility=bad 1000
    switch trail_visibility=horrible 2000
    switch trail_visibility=no 10000
    300  # default

# Surface-based costs
assign costfactor =
    switch surface=paved 1.0
    switch surface=gravel 1.2
    switch surface=ground 1.5
    switch surface=grass 1.8
    switch surface=sand 2.5
    switch surface=rock 3.0
    switch surface=mud 4.0
    switch surface=ice 5.0
    switch surface=snow 2.0  # Good with skis
    1.5  # unknown surface

# Norwegian-specific rules
assign dnt_bonus =
    if operator=DNT then 0.7  # Prefer DNT trails
    else if operator=Kommune then 0.9
    else 1.0

# Seasonal adjustments
assign seasonal_factor =
    if seasonal_mode then
        if surface=mud|grass|ground then 2.0  # Worse in winter
        else if surface=snow|ice then 0.5      # Better in winter
        else 1.0
    else 1.0

# Combine all factors
assign cost =
    multiply costfactor
    multiply dnt_bonus
    multiply seasonal_factor

---context:node
# Node-level decisions (intersections, barriers)
assign initialcost =
    switch barrier=gate 100
    switch barrier=stile 200
    switch barrier=cattle_grid 50
    switch ford=yes 1000
    switch amenity=shelter 0  # No cost for shelters
    0
```

### 2. Advanced Profile Features

#### Mathematical Operations
```ini
# Complex calculations
assign uphillcost =
    max 0                          # Not negative
    min 100                        # Cap at 100
    add uphillbase                 # Base cost
    multiply elevation_factor      # Elevation multiplier

assign slope_penalty =
    if gradient>20 then exp(gradient/10)  # Exponential penalty
    else linear_factor(gradient)          # Linear for moderate

# Trigonometric functions
assign heading_penalty =
    multiply 1.0
    add multiply(cos(heading_diff), 0.5)
```

#### Conditional Logic
```ini
# Nested conditions
assign trail_cost =
    if sac_scale=T1|T2 then
        if weather=good then 1.0
        else if weather=rain then 1.5
        else 2.0
    else if sac_scale=T3|T4 then
        if experienced_hiker then 2.0
        else 10000  # Block for beginners
    else if sac_scale=T5|T6 then
        99999  # Effectively blocked
    else 1.5

# Switch statements
assign time_factor =
    switch season=summer 1.0
    switch season=autumn 1.2
    switch season=winter 1.8
    switch season=spring 1.5
    1.3  # unknown season
```

### 3. Data Tag Customization

#### Custom OSM Tags
```ini
# BRouter can read any OSM tag
assign norwegian_trail =
    or operator=DNT
    or operator="Den Norske Turistforening"
    or network=nwn  # Norwegian walking network

assign difficulty =
    switch trail:difficulty=novice 1.0
    switch trail:difficulty=easy 1.2
    switch trail:difficulty=intermediate 1.8
    switch trail:difficulty=advanced 3.0
    switch trail:difficulty=expert 5.0
    switch norwegian:difficulty=grønn 1.0
    switch norwegian:difficulty=blå 1.5
    switch norwegian:difficulty=rød 2.5
    switch norwegian:difficulty=svart 4.0
    2.0  # unknown
```

#### AR5 Land Cover Integration
```ini
# Use custom land cover tags
assign landcover_cost =
    switch ar5:type=30 1.0   # Forest high
    switch ar5:type=31 1.1   # Forest medium
    switch ar5:type=32 1.3   # Forest low
    switch ar5:type=50 0.9   # Open ground
    switch ar5:type=53 3.0   # Wetland
    switch ar5:type=60 5.0   # Bog
    switch ar5:type=70 2.5   # Rock
    1.5  # default
```

### 4. Profile Modes and Variants

#### Multiple Profiles for Different Conditions
```bash
# profiles2/ directory structure
profiles2/
├── norwegian_summer_hiking.brf
├── norwegian_winter_skiing.brf
├── norwegian_family_hiking.brf
├── norwegian_expert_mountaineering.brf
├── norwegian_bike_trails.brf
└── norwegian_accessibility.brf
```

#### Dynamic Profile Selection
```ini
# Master profile that switches based on conditions
---context:global
assign profile_mode =
    if winter_conditions then "skiing"
    else if family_group then "easy"
    else if expert_mode then "technical"
    else "standard"

---context:way
assign base_cost =
    switch profile_mode=skiing
        switch surface=snow 0.5
        switch surface=ice 2.0
        1.0
    switch profile_mode=easy
        switch sac_scale=T1 1.0
        switch sac_scale=T2 1.5
        99999  # Block harder trails
    switch profile_mode=technical
        switch sac_scale=T4|T5 1.0
        switch sac_scale=T3 1.2
        switch sac_scale=T1|T2 1.5
        1.0
    1.0  # standard mode
```

### 5. Kinematic Model Customization

#### Speed and Time Calculations
```ini
---context:global
assign vmax = 5.0  # Max speed km/h
assign vmin = 1.0  # Min speed km/h

# Elevation speed adjustments
assign downhillspeed =
    multiply vmax 1.2  # 20% faster downhill

assign uphillspeed =
    multiply vmax 0.6  # 40% slower uphill

---context:way
# Dynamic speed based on surface
assign maxspeed =
    switch surface=paved vmax
    switch surface=gravel multiply(vmax, 0.8)
    switch surface=ground multiply(vmax, 0.6)
    switch surface=sand multiply(vmax, 0.4)
    switch surface=rock multiply(vmax, 0.3)
    vmin  # Minimum speed for unknown
```

### 6. Safety and Avoidance Rules

#### Hazard Avoidance
```ini
# Avoid dangerous conditions
assign hazard_penalty =
    if avalanche_risk=high then 99999
    else if avalanche_risk=moderate then 1000
    else if river_crossing=yes then
        if season=spring then 99999  # Spring melt
        else 500
    else if cliff_exposure=yes then 2000
    else 0

# Time-based restrictions
assign time_restriction =
    if hunting_season=yes then
        if dayofweek=weekend then 99999
        else 10
    else if bird_nesting=yes then
        if month>=4 and month<=7 then 99999
        else 0
    else 0
```

## Comparison with GraphHopper

| Feature | BRouter | GraphHopper |
|---------|---------|-------------|
| **Customization Method** | Profile DSL | Java code + YAML |
| **No-Code Customization** | ✅ Full routing logic | ⚠️ Limited to weights |
| **Mathematical Operations** | ✅ Built-in functions | ✅ Java flexibility |
| **Conditional Logic** | ✅ Extensive | ✅ Full programming |
| **Custom Tags** | ✅ Any OSM tag | ✅ With encoding |
| **Performance** | ⚡ Very fast | ⚡ Fast with more overhead |
| **Learning Curve** | 📊 Moderate (DSL) | 📊 Steep (Java) |
| **Debugging** | ⚠️ Limited tools | ✅ Full IDE support |
| **3D Support** | ❌ None | ⚠️ Can be added |
| **API Flexibility** | ⚠️ Basic | ✅ Full REST API |

## Advanced Customization Examples

### 1. Scenic Route Profile
```ini
---context:way
# Prefer trails with views
assign scenic_bonus =
    if tourism=viewpoint then 0.3
    else if natural=peak then 0.4
    else if natural=ridge then 0.5
    else if landuse=forest then 1.2  # Avoid dense forest
    else 1.0

assign scenic_cost =
    multiply base_cost scenic_bonus
```

### 2. Weather-Adaptive Routing
```ini
---context:global
assign weather = "rain"  # Set dynamically

---context:way
assign weather_factor =
    if weather=rain then
        switch surface=rock 3.0      # Slippery
        switch surface=grass 2.0     # Muddy
        switch surface=paved 0.9     # Better in rain
        1.5
    else if weather=snow then
        switch surface=paved 2.0     # May be icy
        switch surface=ground 1.0    # Snow cover OK
        1.3
    else 1.0  # Good weather
```

### 3. Group-Specific Routing
```ini
---context:global
assign group_type = "family_with_children"

---context:way
assign group_suitability =
    switch group_type=family_with_children
        and width>1.5               # Wide enough
        and sac_scale=T1           # Easy only
        and not ford=yes            # No water crossing
        and distance_to_parking<5000 # Not too far
        then 0.5                    # Prefer these
    switch group_type=elderly
        and surface=paved|gravel
        and incline<5
        then 0.6
    switch group_type=athletes
        and sac_scale=T3|T4|T5
        then 0.7
    1.0  # Default
```

## Limitations

### What BRouter CANNOT Customize:
1. **Core Algorithm**: A* pathfinding is fixed
2. **Data Storage**: RD5 format is fixed
3. **Visualization**: No built-in map or 3D
4. **Network Topology**: Cannot modify graph structure
5. **Real-time Data**: No dynamic data integration
6. **Plugins**: No plugin architecture

### What BRouter CAN Customize:
1. **All routing decisions** via profiles
2. **Any OSM tag** interpretation
3. **Complex cost calculations**
4. **Seasonal/conditional routing**
5. **Speed/time estimations**
6. **Turn costs and restrictions**

## Creating Custom Profiles

### Step 1: Start with Template
```bash
cp profiles2/trekking.brf profiles2/norwegian_custom.brf
```

### Step 2: Test Profile
```bash
# Test routing with custom profile
java -jar brouter.jar \
  routing \
  --profile norwegian_custom \
  --lonlats "10.7522,59.9139|10.7389,59.9275"
```

### Step 3: Debug Output
```ini
---context:global
assign debug = true  # Enable debug output

---context:way
assign debugmsg =
    concat "Surface: " surface
    concat " | Cost: " cost
    concat " | SAC: " sac_scale
```

## Deployment

### Server Configuration
```properties
# brouter.properties
profilePath = ./profiles2
customProfilesAllowed = true
maxProfileSize = 100000
profileCacheSize = 50
```

### Web Interface Customization
```javascript
// Add custom profiles to web UI
BR.conf.profiles = [
    'norwegian_summer',
    'norwegian_winter',
    'norwegian_family',
    'norwegian_expert'
];
```

## Best Practices

1. **Start Simple**: Begin with existing profile, modify gradually
2. **Comment Extensively**: Document your logic
3. **Test Edge Cases**: Check extreme conditions
4. **Version Control**: Keep profile versions
5. **Performance Test**: Complex logic can slow routing

## Conclusion

BRouter is **extremely customizable** for routing logic through its profile system. While it lacks GraphHopper's plugin architecture and API flexibility, its profile DSL is more powerful for routing decisions without requiring programming knowledge. For Norwegian trail routing, BRouter's customization is sufficient for:

- ✅ Complex trail difficulty assessment
- ✅ Seasonal routing variations
- ✅ Land cover integration
- ✅ Safety and hazard avoidance
- ✅ Group-specific routing

But it cannot be customized for:
- ❌ 3D visualization
- ❌ Custom data formats
- ❌ Real-time data integration
- ❌ API response format
