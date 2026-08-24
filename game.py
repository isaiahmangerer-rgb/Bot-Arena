"""
BOT ARENA — DELUXE SINGLE-FILE EDITION
======================================

Install:
    pip install flask flask-socketio

Run:
    python game.py

Open:
    http://127.0.0.1:5000

Everything lives in this file:
- Flask/Socket.IO server
- authoritative game simulation
- waves, elites, bosses, difficulty scaling
- XP/levels and upgrade choices
- weapons and polished shop
- dash + grenade abilities
- pickups
- combo/scoring system
- solo, co-op and FFA
- responsive HTML/CSS/Canvas frontend
"""

import math
import random
import time
import uuid
from threading import Lock

from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit, join_room


# ============================================================================
# SERVER CONFIG
# ============================================================================

app = Flask(__name__)
app.config["SECRET_KEY"] = "bot-arena-deluxe-secret"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_interval=25,
    ping_timeout=60,
)

WORLD_W = 1600
WORLD_H = 900
MAX_PLAYERS = 8
TICK_RATE = 30
STATE_RATE = 20
ROOM_CLEANUP_SECONDS = 180

MODE_NAMES = {
    "solo": "SOLO",
    "multiplayer": "CO-OP",
    "ffa": "FREE FOR ALL",
}

rooms = {}
sid_room = {}
lock = Lock()


# ============================================================================
# CONTENT
# ============================================================================

WEAPONS = {
    "pistol": {
        "name": "Pulse Pistol",
        "description": "Reliable starter sidearm.",
        "damage": 24,
        "fire_rate": 5.5,
        "speed": 1050,
        "spread": 0.018,
        "pellets": 1,
        "magazine": 14,
        "price": 0,
        "color": "#64d9ff",
    },
    "smg": {
        "name": "Viper SMG",
        "description": "Very fast fire rate with manageable spread.",
        "damage": 12,
        "fire_rate": 15,
        "speed": 1120,
        "spread": 0.105,
        "pellets": 1,
        "magazine": 38,
        "price": 300,
        "color": "#9cff6a",
    },
    "shotgun": {
        "name": "Thunder Shotgun",
        "description": "Eight projectiles. Devastating up close.",
        "damage": 17,
        "fire_rate": 1.55,
        "speed": 760,
        "spread": 0.29,
        "pellets": 8,
        "magazine": 8,
        "price": 600,
        "color": "#ffb45c",
    },
    "rifle": {
        "name": "Sentinel Rifle",
        "description": "Hard-hitting, accurate automatic rifle.",
        "damage": 46,
        "fire_rate": 4.2,
        "speed": 1420,
        "spread": 0.012,
        "pellets": 1,
        "magazine": 22,
        "price": 950,
        "color": "#d8b4ff",
    },
    "laser": {
        "name": "Ion Laser",
        "description": "Extremely accurate rapid-fire energy weapon.",
        "damage": 19,
        "fire_rate": 18,
        "speed": 1700,
        "spread": 0.006,
        "pellets": 1,
        "magazine": 50,
        "price": 1450,
        "color": "#ff6ee8",
    },
    "railgun": {
        "name": "Rail Cannon",
        "description": "Slow, expensive, armor-piercing monster.",
        "damage": 180,
        "fire_rate": 0.9,
        "speed": 2200,
        "spread": 0.004,
        "pellets": 1,
        "magazine": 5,
        "price": 2200,
        "color": "#fff08a",
    },
}

SHOP_ITEMS = {
    "medkit": {
        "name": "Nano Medkit",
        "description": "Restore 55 health immediately.",
        "price": 160,
        "icon": "✚",
    },
    "armor": {
        "name": "Titan Plating",
        "description": "+30 maximum health and heal 30.",
        "price": 340,
        "icon": "⬢",
    },
    "speed": {
        "name": "Velocity Core",
        "description": "+24 movement speed.",
        "price": 430,
        "icon": "➤",
    },
    "damage": {
        "name": "Overclock Chip",
        "description": "+12% weapon damage.",
        "price": 620,
        "icon": "ϟ",
    },
    "shield": {
        "name": "Energy Shield",
        "description": "Reduce incoming damage by 8%.",
        "price": 760,
        "icon": "◈",
    },
    "ammo": {
        "name": "Ammo Cache",
        "description": "Completely refill your current magazine.",
        "price": 110,
        "icon": "▣",
    },
    "magazine": {
        "name": "Extended Magazine",
        "description": "+25% magazine capacity.",
        "price": 520,
        "icon": "▤",
    },
    "critical": {
        "name": "Targeting AI",
        "description": "+5% critical hit chance.",
        "price": 900,
        "icon": "◎",
    },
    "regen": {
        "name": "Nanobot Repair",
        "description": "+3.5 health regenerated every second.",
        "price": 720,
        "icon": "♥",
    },
    "grenade": {
        "name": "Shock Grenade",
        "description": "+1 grenade charge, maximum 6.",
        "price": 300,
        "icon": "●",
    },
    "dash": {
        "name": "Phase Drive",
        "description": "Reduces dash cooldown by 12%.",
        "price": 650,
        "icon": "»",
    },
    "overdrive": {
        "name": "Overdrive Module",
        "description": "Adds 20 seconds of boosted damage and speed.",
        "price": 1150,
        "icon": "⚡",
    },
}

ENEMIES = {
    "drone": {
        "health": 78,
        "speed": 105,
        "damage": 11,
        "radius": 18,
        "reward": 24,
        "attack": 0.9,
    },
    "runner": {
        "health": 52,
        "speed": 205,
        "damage": 17,
        "radius": 13,
        "reward": 35,
        "attack": 0.55,
    },
    "brute": {
        "health": 380,
        "speed": 58,
        "damage": 34,
        "radius": 29,
        "reward": 95,
        "attack": 1.05,
    },
    "sniper": {
        "health": 145,
        "speed": 72,
        "damage": 48,
        "radius": 20,
        "reward": 120,
        "attack": 1.8,
    },
    "tank": {
        "health": 950,
        "speed": 37,
        "damage": 62,
        "radius": 42,
        "reward": 240,
        "attack": 1.15,
    },
    "boss": {
        "health": 3600,
        "speed": 47,
        "damage": 82,
        "radius": 62,
        "reward": 900,
        "attack": 0.8,
    },
}

# Arena obstacles are visual + collision geometry.
OBSTACLES = [
    {"x": 300, "y": 190, "w": 220, "h": 44},
    {"x": 1080, "y": 190, "w": 220, "h": 44},
    {"x": 300, "y": 666, "w": 220, "h": 44},
    {"x": 1080, "y": 666, "w": 220, "h": 44},
    {"x": 735, "y": 170, "w": 130, "h": 130},
    {"x": 735, "y": 600, "w": 130, "h": 130},
]

PICKUP_TYPES = {
    "coin": {"color": "#ffd45c", "value": 45},
    "heal": {"color": "#58ed8b", "value": 28},
    "ammo": {"color": "#61cfff", "value": 1},
    "energy": {"color": "#c57cff", "value": 1},
}


# ============================================================================
# UTILITY
# ============================================================================

def monotonic():
    return time.monotonic()


def uid():
    return uuid.uuid4().hex[:12]


def clamp(value, low, high):
    return max(low, min(high, value))


def distance(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


def clean_name(value):
    value = str(value or "Player").strip()
    return value[:18] or "Player"


def safe_float(value, default=0.0):
    try:
        result = float(value)
        if math.isfinite(result):
            return result
    except (TypeError, ValueError):
        pass
    return default


def circle_rect_collision(cx, cy, radius, rect):
    nearest_x = clamp(cx, rect["x"], rect["x"] + rect["w"])
    nearest_y = clamp(cy, rect["y"], rect["y"] + rect["h"])
    return math.hypot(cx - nearest_x, cy - nearest_y) <= radius


def collides_obstacle(x, y, radius):
    return any(circle_rect_collision(x, y, radius, r) for r in OBSTACLES)


def move_with_collision(entity, dx, dy, radius):
    nx = clamp(entity["x"] + dx, radius, WORLD_W - radius)
    ny = clamp(entity["y"] + dy, radius, WORLD_H - radius)

    if not collides_obstacle(nx, entity["y"], radius):
        entity["x"] = nx

    if not collides_obstacle(entity["x"], ny, radius):
        entity["y"] = ny


def random_spawn_away(room, minimum=430):
    for _ in range(80):
        side = random.randrange(4)
        margin = 80
        if side == 0:
            x, y = random.uniform(80, WORLD_W - 80), margin
        elif side == 1:
            x, y = WORLD_W - margin, random.uniform(80, WORLD_H - 80)
        elif side == 2:
            x, y = random.uniform(80, WORLD_W - 80), WORLD_H - margin
        else:
            x, y = margin, random.uniform(80, WORLD_H - 80)

        if collides_obstacle(x, y, 45):
            continue

        players = [p for p in room["players"].values() if p["alive"]]
        if not players or all(distance({"x": x, "y": y}, p) >= minimum for p in players):
            return x, y

    return WORLD_W / 2, 80


def spawn_position(index):
    points = [
        (800, 450),
        (720, 450),
        (880, 450),
        (800, 370),
        (800, 530),
        (700, 360),
        (900, 360),
        (900, 540),
    ]
    return points[index % len(points)]


def generate_room_code():
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(random.choice(chars) for _ in range(6))
        if code not in rooms:
            return code


# ============================================================================
# PLAYER
# ============================================================================

def create_player(sid, name, index):
    x, y = spawn_position(index)
    mag = WEAPONS["pistol"]["magazine"]
    return {
        "id": sid,
        "name": clean_name(name),
        "x": x,
        "y": y,
        "radius": 18,
        "health": 110.0,
        "max_health": 110.0,
        "coins": 450,
        "level": 1,
        "xp": 0,
        "kills": 0,
        "deaths": 0,
        "score": 0,
        "combo": 0,
        "combo_timer": 0.0,
        "alive": True,
        "speed": 248.0,
        "damage_multiplier": 1.0,
        "critical": 0.06,
        "shield": 0.0,
        "regen": 0.0,
        "overdrive": 0.0,
        "weapon": "pistol",
        "owned_weapons": {"pistol"},
        "ammo": mag,
        "magazine": mag,
        "last_shot": 0.0,
        "last_damage": 0.0,
        "move_dx": 0.0,
        "move_dy": 0.0,
        "dash_cd": 0.0,
        "dash_power": 560.0,
        "grenades": 2,
        "max_grenades": 2,
        "grenade_cd": 0.0,
        "revive_cost": 500,
        "invuln": 0.0,
        "kills_this_wave": 0,
        "damage_taken": 0.0,
    }


# ============================================================================
# ROOM
# ============================================================================

def create_room(mode):
    if mode not in MODE_NAMES:
        mode = "solo"

    code = generate_room_code()

    room = {
        "code": code,
        "mode": mode,
        "players": {},
        "enemies": [],
        "bullets": [],
        "grenades": [],
        "pickups": [],
        "particles": [],
        "wave": 0,
        "score": 0,
        "started": False,
        "game_over": False,
        "paused": False,
        "shop_paused_by": None,
        "squad_eliminated": False,
        "revive_cost": 1000,
        "revive_count": {},
        "intermission": 0.0,
        "wave_spawn_left": 0,
        "wave_total": 0,
        "wave_spawn_timer": 0.0,
        "wave_clear_bonus_given": False,
        "announcement": "READY",
        "announcement_timer": 2.5,
        "created": monotonic(),
        "last_update": monotonic(),
        "last_state": 0.0,
    }
    rooms[code] = room
    return room


# ============================================================================
# XP / DAMAGE
# ============================================================================

def xp_needed(player):
    return 100 + (player["level"] - 1) * 55


def give_xp(player, amount):
    player["xp"] += max(0, int(amount))
    levels = 0

    while player["xp"] >= xp_needed(player):
        player["xp"] -= xp_needed(player)
        player["level"] += 1
        player["max_health"] += 18
        player["health"] = player["max_health"]
        player["speed"] += 5
        player["damage_multiplier"] += 0.025
        levels += 1

    return levels


def damage_player(player, amount):
    if not player["alive"] or player["invuln"] > 0:
        return False

    amount = max(0.0, amount)
    reduction = clamp(player["shield"], 0.0, 0.70)
    final = amount * (1.0 - reduction)
    player["health"] -= final
    player["damage_taken"] += final
    player["last_damage"] = monotonic()

    if player["health"] <= 0:
        player["health"] = 0
        player["alive"] = False
        player["deaths"] += 1
        player["move_dx"] = 0
        player["move_dy"] = 0
        player["combo"] = 0
        return True

    return False


def revive_player(player):
    if player["alive"] or player["coins"] < player["revive_cost"]:
        return False

    player["coins"] -= player["revive_cost"]
    player["revive_cost"] = int(player["revive_cost"] * 1.55)
    player["alive"] = True
    player["health"] = player["max_health"] * 0.52
    player["x"] = WORLD_W / 2
    player["y"] = WORLD_H / 2
    player["invuln"] = 2.5
    return True


# ============================================================================
# WAVES
# ============================================================================

def wave_difficulty(room):
    wave = room["wave"]
    player_count = max(1, len(room["players"]))

    # Deliberately harder than the previous version.
    health = 1.0 + wave * 0.145 + max(0, player_count - 1) * 0.10
    speed = 1.0 + wave * 0.020
    damage = 1.0 + wave * 0.115 + max(0, player_count - 1) * 0.055
    return health, speed, damage


def enemy_pool(wave):
    pool = ["drone", "drone", "drone", "runner"]

    if wave >= 3:
        pool += ["runner", "brute"]
    if wave >= 5:
        pool += ["sniper"]
    if wave >= 7:
        pool += ["brute", "tank"]
    if wave >= 10:
        pool += ["sniper", "tank"]
    if wave >= 13:
        pool += ["tank", "runner", "brute"]

    return pool


def start_wave(room):
    room["wave"] += 1
    wave = room["wave"]

    health_mult, speed_mult, damage_mult = wave_difficulty(room)

    # More enemies and less breathing room.
    base = 7 + wave * 3
    player_bonus = max(0, len(room["players"]) - 1) * (2 + wave // 5)
    amount = base + player_bonus

    if wave % 5 == 0:
        room["wave_spawn_left"] = max(1, amount - 2)
        create_enemy(room, "boss", health_mult, speed_mult, damage_mult)
        room["announcement"] = f"BOSS WAVE {wave}"
        room["announcement_timer"] = 3.5
    else:
        room["wave_spawn_left"] = amount
        room["announcement"] = f"WAVE {wave}"
        room["announcement_timer"] = 2.8

    room["wave_total"] = room["wave_spawn_left"] + len(room["enemies"])
    room["wave_spawn_timer"] = 0.0
    room["intermission"] = 0.0
    room["wave_clear_bonus_given"] = False

    for player in room["players"].values():
        player["kills_this_wave"] = 0
        player["damage_taken"] = 0


def create_enemy(room, enemy_type, health_mult=None, speed_mult=None, damage_mult=None):
    data = ENEMIES[enemy_type]

    if health_mult is None:
        health_mult, speed_mult, damage_mult = wave_difficulty(room)

    x, y = random_spawn_away(room, 500 if enemy_type != "boss" else 620)

    elite = enemy_type != "boss" and random.random() < min(0.035 + room["wave"] * 0.008, 0.16)
    elite_mult = 1.65 if elite else 1.0

    max_health = data["health"] * health_mult * elite_mult

    enemy = {
        "id": uid(),
        "type": enemy_type,
        "x": x,
        "y": y,
        "health": max_health,
        "max_health": max_health,
        "speed": data["speed"] * speed_mult * (1.08 if elite else 1.0),
        "damage": data["damage"] * damage_mult * (1.20 if elite else 1.0),
        "radius": data["radius"] * (1.08 if elite else 1.0),
        "reward": int(data["reward"] * health_mult * (1.5 if elite else 1.0)),
        "attack_timer": random.uniform(0.2, 1.0),
        "hit_flash": 0.0,
        "elite": elite,
        "shoot_timer": random.uniform(1.0, 2.5),
    }

    room["enemies"].append(enemy)


def update_wave_spawning(room, dt):
    if room["wave"] <= 0:
        start_wave(room)
        return

    if room["wave_spawn_left"] <= 0:
        return

    room["wave_spawn_timer"] -= dt
    if room["wave_spawn_timer"] > 0:
        return

    room["wave_spawn_timer"] = max(0.12, 0.75 - room["wave"] * 0.012)

    enemy_type = random.choice(enemy_pool(room["wave"]))
    create_enemy(room, enemy_type)
    room["wave_spawn_left"] -= 1


def update_wave_progress(room, dt):
    if room["wave"] <= 0:
        return

    if room["wave_spawn_left"] > 0 or room["enemies"]:
        return

    if room["intermission"] <= 0:
        room["intermission"] = 5.0
        room["announcement"] = "WAVE CLEARED"
        room["announcement_timer"] = 2.4

        if not room["wave_clear_bonus_given"]:
            room["wave_clear_bonus_given"] = True
            bonus = 100 + room["wave"] * 35
            room["score"] += bonus
            for player in room["players"].values():
                if player["alive"]:
                    player["coins"] += bonus // max(1, len(room["players"]))
                    give_xp(player, 35 + room["wave"] * 4)

    else:
        room["intermission"] -= dt
        if room["intermission"] <= 0:
            start_wave(room)


# ============================================================================
# ENEMY AI
# ============================================================================

def nearest_player(room, source):
    candidates = [p for p in room["players"].values() if p["alive"]]
    if not candidates:
        return None
    return min(candidates, key=lambda p: distance(p, source))


def nearest_enemy(room, source):
    candidates = [e for e in room["enemies"] if e["health"] > 0]
    if not candidates:
        return None
    return min(candidates, key=lambda e: distance(e, source))


def enemy_projectile(room, enemy, target):
    dx = target["x"] - enemy["x"]
    dy = target["y"] - enemy["y"]
    d = math.hypot(dx, dy) or 1.0

    room["bullets"].append({
        "id": uid(),
        "owner": enemy["id"],
        "enemy": True,
        "x": enemy["x"],
        "y": enemy["y"],
        "dx": dx / d * 460,
        "dy": dy / d * 460,
        "damage": enemy["damage"] * 0.75,
        "life": 3.2,
        "radius": 6,
    })


def update_enemies(room, dt):
    for enemy in room["enemies"]:
        if enemy["health"] <= 0:
            continue

        enemy["hit_flash"] = max(0.0, enemy["hit_flash"] - dt)
        target = nearest_player(room, enemy)

        if target is None:
            continue

        dx = target["x"] - enemy["x"]
        dy = target["y"] - enemy["y"]
        d = math.hypot(dx, dy) or 1.0

        # Snipers and elites have ranged behavior.
        if enemy["type"] in ("sniper", "boss") and d < 720:
            if enemy["type"] == "boss" or d > 310:
                enemy["shoot_timer"] -= dt
                if enemy["shoot_timer"] <= 0:
                    enemy_projectile(room, enemy, target)
                    enemy["shoot_timer"] = 1.45 if enemy["type"] == "boss" else 2.35

        contact = enemy["radius"] + target["radius"] + 8

        if d > contact:
            # Bosses periodically accelerate toward the player.
            boost = 1.0
            if enemy["type"] == "boss" and int(monotonic() * 2) % 7 == 0:
                boost = 1.35

            move_with_collision(
                enemy,
                dx / d * enemy["speed"] * boost * dt,
                dy / d * enemy["speed"] * boost * dt,
                enemy["radius"],
            )
        else:
            enemy["attack_timer"] -= dt
            if enemy["attack_timer"] <= 0:
                died = damage_player(target, enemy["damage"])
                enemy["attack_timer"] = ENEMIES[enemy["type"]]["attack"]

                if died:
                    room["announcement"] = f"{target['name']} WAS DOWNED"
                    room["announcement_timer"] = 1.4


# ============================================================================
# WEAPONS / PROJECTILES
# ============================================================================

def fire_weapon(room, player, angle):
    if not player["alive"]:
        return False

    weapon = WEAPONS[player["weapon"]]
    current = monotonic()

    if current - player["last_shot"] < 1.0 / weapon["fire_rate"]:
        return False

    if player["ammo"] <= 0:
        return False

    player["last_shot"] = current
    player["ammo"] -= 1

    damage_multiplier = player["damage_multiplier"]
    if player["overdrive"] > 0:
        damage_multiplier *= 1.45

    for _ in range(weapon["pellets"]):
        spread = random.uniform(-weapon["spread"], weapon["spread"])
        a = angle + spread

        room["bullets"].append({
            "id": uid(),
            "owner": player["id"],
            "enemy": False,
            "x": player["x"] + math.cos(a) * 25,
            "y": player["y"] + math.sin(a) * 25,
            "dx": math.cos(a) * weapon["speed"],
            "dy": math.sin(a) * weapon["speed"],
            "damage": weapon["damage"] * damage_multiplier,
            "life": 1.6,
            "radius": 4 if weapon["pellets"] == 1 else 3,
        })

    return True


def award_kill(room, enemy, owner):
    reward = enemy["reward"]

    if owner is not None:
        owner["kills"] += 1
        owner["kills_this_wave"] += 1
        owner["coins"] += reward
        owner["combo"] += 1
        owner["combo_timer"] = 3.2

        combo_mult = min(3.0, 1.0 + owner["combo"] * 0.08)
        owner["score"] += int(reward * combo_mult)
        give_xp(owner, reward)

        # Chance for a useful pickup.
        if random.random() < 0.18:
            create_pickup(room, enemy["x"], enemy["y"])

    room["score"] += reward


def update_bullets(room, dt):
    alive_bullets = []
    dead_enemies = set()

    for bullet in room["bullets"]:
        bullet["x"] += bullet["dx"] * dt
        bullet["y"] += bullet["dy"] * dt
        bullet["life"] -= dt

        if bullet["life"] <= 0:
            continue
        if not (-50 <= bullet["x"] <= WORLD_W + 50):
            continue
        if not (-50 <= bullet["y"] <= WORLD_H + 50):
            continue

        hit = False

        if bullet.get("enemy"):
            for player in room["players"].values():
                if not player["alive"]:
                    continue
                if distance(bullet, player) <= player["radius"] + bullet.get("radius", 4):
                    damage_player(player, bullet["damage"])
                    hit = True
                    break
        else:
            for enemy in room["enemies"]:
                if enemy["id"] in dead_enemies or enemy["health"] <= 0:
                    continue

                if distance(bullet, enemy) <= enemy["radius"] + bullet.get("radius", 4):
                    owner = room["players"].get(bullet["owner"])
                    damage = bullet["damage"]

                    # Railgun partially ignores shields/armor conceptually.
                    if owner and owner["weapon"] == "railgun":
                        damage *= 1.35

                    critical = owner is not None and random.random() < owner["critical"]
                    if critical:
                        damage *= 2.0

                    enemy["health"] -= damage
                    enemy["hit_flash"] = 0.09
                    hit = True

                    if enemy["health"] <= 0:
                        dead_enemies.add(enemy["id"])
                        award_kill(room, enemy, owner)
                    break

        if not hit:
            alive_bullets.append(bullet)

    room["bullets"] = alive_bullets

    if dead_enemies:
        for enemy in room["enemies"]:
            if enemy["id"] in dead_enemies:
                # Bosses have a much better pickup chance.
                if enemy["type"] == "boss":
                    for _ in range(4):
                        create_pickup(room, enemy["x"] + random.uniform(-35, 35),
                                      enemy["y"] + random.uniform(-35, 35))
        room["enemies"] = [
            e for e in room["enemies"] if e["id"] not in dead_enemies
        ]


# ============================================================================
# ABILITIES
# ============================================================================

def use_dash(player, angle):
    if not player["alive"] or player["dash_cd"] > 0:
        return False

    dx = math.cos(angle)
    dy = math.sin(angle)

    # Move in a few smaller collision-aware increments.
    for _ in range(7):
        move_with_collision(
            player,
            dx * player["dash_power"] / 7,
            dy * player["dash_power"] / 7,
            player["radius"],
        )

    player["dash_cd"] = 3.8
    player["invuln"] = 0.28
    return True


def use_grenade(room, player, x, y):
    if not player["alive"] or player["grenades"] <= 0 or player["grenade_cd"] > 0:
        return False

    x = clamp(x, 0, WORLD_W)
    y = clamp(y, 0, WORLD_H)

    player["grenades"] -= 1
    player["grenade_cd"] = 0.45

    room["grenades"].append({
        "id": uid(),
        "owner": player["id"],
        "x": x,
        "y": y,
        "timer": 0.65,
        "radius": 170,
        "damage": 220 * player["damage_multiplier"],
    })
    return True


def update_grenades(room, dt):
    active = []

    for grenade in room["grenades"]:
        grenade["timer"] -= dt

        if grenade["timer"] > 0:
            active.append(grenade)
            continue

        for enemy in room["enemies"]:
            d = distance(grenade, enemy)
            if d <= grenade["radius"]:
                falloff = 1.0 - (d / grenade["radius"]) * 0.55
                enemy["health"] -= grenade["damage"] * falloff
                enemy["hit_flash"] = 0.12

        # Damage players in FFA, but never the thrower.
        if room["mode"] == "ffa":
            for p in room["players"].values():
                if p["id"] != grenade["owner"] and p["alive"]:
                    d = distance(grenade, p)
                    if d <= grenade["radius"]:
                        falloff = 1.0 - (d / grenade["radius"]) * 0.55
                        damage_player(p, grenade["damage"] * 0.25 * falloff)

    room["grenades"] = active


# ============================================================================
# PICKUPS
# ============================================================================

def create_pickup(room, x, y):
    kind = random.choice(list(PICKUP_TYPES))
    room["pickups"].append({
        "id": uid(),
        "type": kind,
        "x": clamp(x, 25, WORLD_W - 25),
        "y": clamp(y, 25, WORLD_H - 25),
        "life": 15.0,
    })


def collect_pickups(room, dt):
    remaining = []

    for pickup in room["pickups"]:
        pickup["life"] -= dt
        if pickup["life"] <= 0:
            continue

        collected = False

        for player in room["players"].values():
            if not player["alive"]:
                continue
            if distance(pickup, player) > 34:
                continue

            kind = pickup["type"]
            if kind == "coin":
                player["coins"] += PICKUP_TYPES[kind]["value"]
            elif kind == "heal":
                player["health"] = min(
                    player["max_health"],
                    player["health"] + PICKUP_TYPES[kind]["value"],
                )
            elif kind == "ammo":
                player["ammo"] = player["magazine"]
            elif kind == "energy":
                player["grenades"] = min(player["max_grenades"], player["grenades"] + 1)

            player["score"] += 25
            collected = True
            break

        if not collected:
            remaining.append(pickup)

    room["pickups"] = remaining


# ============================================================================
# PLAYER UPDATE
# ============================================================================

def update_players(room, dt):
    for player in room["players"].values():
        player["dash_cd"] = max(0.0, player["dash_cd"] - dt)
        player["grenade_cd"] = max(0.0, player["grenade_cd"] - dt)
        player["invuln"] = max(0.0, player["invuln"] - dt)
        player["overdrive"] = max(0.0, player["overdrive"] - dt)
        player["combo_timer"] = max(0.0, player["combo_timer"] - dt)

        if player["combo_timer"] <= 0:
            player["combo"] = 0

        if not player["alive"]:
            continue

        dx = clamp(player["move_dx"], -1, 1)
        dy = clamp(player["move_dy"], -1, 1)
        length = math.hypot(dx, dy)

        if length > 0:
            dx /= length
            dy /= length

            speed = player["speed"]
            if player["overdrive"] > 0:
                speed *= 1.32

            move_with_collision(
                player,
                dx * speed * dt,
                dy * speed * dt,
                player["radius"],
            )

        if player["regen"] > 0:
            player["health"] = min(
                player["max_health"],
                player["health"] + player["regen"] * dt,
            )


# ============================================================================
# SHOP
# ============================================================================

def buy_item(player, item_id):
    item = SHOP_ITEMS.get(item_id)
    if not item:
        return False, "Unknown item."

    if player["coins"] < item["price"]:
        return False, "Not enough coins."

    # Limits prevent upgrades from becoming silly.
    if item_id == "shield" and player["shield"] >= 0.70:
        return False, "Shield is already maxed."
    if item_id == "critical" and player["critical"] >= 0.75:
        return False, "Critical chance is already maxed."
    if item_id == "grenade" and player["max_grenades"] >= 6:
        return False, "Grenade capacity is maxed."

    player["coins"] -= item["price"]

    if item_id == "medkit":
        player["health"] = min(player["max_health"], player["health"] + 55)
    elif item_id == "armor":
        player["max_health"] += 30
        player["health"] = min(player["max_health"], player["health"] + 30)
    elif item_id == "speed":
        player["speed"] += 24
    elif item_id == "damage":
        player["damage_multiplier"] += 0.12
    elif item_id == "shield":
        player["shield"] += 0.08
    elif item_id == "ammo":
        player["ammo"] = player["magazine"]
    elif item_id == "magazine":
        player["magazine"] = max(
            player["magazine"] + 1,
            int(math.ceil(player["magazine"] * 1.25)),
        )
        player["ammo"] = player["magazine"]
    elif item_id == "critical":
        player["critical"] += 0.05
    elif item_id == "regen":
        player["regen"] += 3.5
    elif item_id == "grenade":
        player["max_grenades"] += 1
        player["grenades"] = player["max_grenades"]
    elif item_id == "dash":
        player["dash_power"] += 25
        player["dash_cd"] = min(player["dash_cd"], 1.0)
    elif item_id == "overdrive":
        player["overdrive"] = max(player["overdrive"], 20.0)

    return True, f"{item['name']} purchased."


def buy_weapon(player, weapon_id):
    weapon = WEAPONS.get(weapon_id)
    if not weapon:
        return False, "Unknown weapon."

    if weapon_id in player["owned_weapons"]:
        player["weapon"] = weapon_id
        player["magazine"] = max(player["magazine"], weapon["magazine"])
        player["ammo"] = player["magazine"]
        return True, f"{weapon['name']} equipped."

    if player["coins"] < weapon["price"]:
        return False, "Not enough coins."

    player["coins"] -= weapon["price"]
    player["owned_weapons"].add(weapon_id)
    player["weapon"] = weapon_id
    player["magazine"] = weapon["magazine"]
    player["ammo"] = weapon["magazine"]

    return True, f"{weapon['name']} unlocked."


# ============================================================================
# FFA
# ============================================================================

def ffa_attack(room, attacker, target_id):
    if room["mode"] != "ffa" or not attacker["alive"]:
        return False

    target = room["players"].get(target_id)
    if not target or not target["alive"] or target["id"] == attacker["id"]:
        return False

    if distance(attacker, target) > 700:
        return False

    damage = 23.0 * attacker["damage_multiplier"]
    if attacker["overdrive"] > 0:
        damage *= 1.45
    if random.random() < attacker["critical"]:
        damage *= 2

    if damage_player(target, damage):
        attacker["kills"] += 1
        attacker["coins"] += 150
        attacker["score"] += 300
        give_xp(attacker, 150)

    return True


# ============================================================================
# SERIALIZATION
# ============================================================================

def public_player(p):
    return {
        "id": p["id"],
        "name": p["name"],
        "x": round(p["x"], 1),
        "y": round(p["y"], 1),
        "health": round(p["health"]),
        "max_health": round(p["max_health"]),
        "coins": p["coins"],
            "revives": p.get("revives", 0),
            "revive_cost": 1000 * (2 ** p.get("revives", 0)),
        "level": p["level"],
        "xp": p["xp"],
        "xp_needed": xp_needed(p),
        "kills": p["kills"],
        "deaths": p["deaths"],
        "score": p["score"],
        "combo": p["combo"],
        "alive": p["alive"],
        "weapon": p["weapon"],
        "ammo": p["ammo"],
        "magazine": p["magazine"],
        "owned_weapons": sorted(p["owned_weapons"]),
        "dash_cd": round(p["dash_cd"], 1),
        "grenades": p["grenades"],
        "max_grenades": p["max_grenades"],
        "grenade_cd": round(p["grenade_cd"], 1),
        "overdrive": round(p["overdrive"], 1),
        "shield": round(p["shield"], 2),
        "critical": round(p["critical"], 2),
        "revive_cost": p["revive_cost"],
    }


def public_enemy(e):
    return {
        "id": e["id"],
        "type": e["type"],
        "x": round(e["x"], 1),
        "y": round(e["y"], 1),
        "health": round(e["health"]),
        "max_health": round(e["max_health"]),
        "radius": round(e["radius"]),
        "elite": e["elite"],
        "hit_flash": e["hit_flash"] > 0,
    }


def get_state(room):
    return {
        "code": room["code"],
        "mode": room["mode"],
        "mode_name": MODE_NAMES[room["mode"]],
        "started": room["started"],
        "game_over": room["game_over"],
        "paused": room["paused"],
        "squad_eliminated": room.get("squad_eliminated", False),
        "wave": room["wave"],
        "score": room["score"],
        "intermission": round(max(0, room["intermission"]), 1),
        "spawn_left": room["wave_spawn_left"],
        "announcement": room["announcement"],
        "announcement_timer": round(max(0, room["announcement_timer"]), 1),
        "players": [public_player(p) for p in room["players"].values()],
        "enemies": [public_enemy(e) for e in room["enemies"]],
        "bullets": [
            {
                "id": b["id"],
                "x": round(b["x"], 1),
                "y": round(b["y"], 1),
                "enemy": bool(b.get("enemy")),
                "owner": b["owner"],
            }
            for b in room["bullets"]
        ],
        "grenades": [
            {
                "id": g["id"],
                "x": round(g["x"], 1),
                "y": round(g["y"], 1),
                "timer": round(max(0, g["timer"]), 2),
                "radius": g["radius"],
            }
            for g in room["grenades"]
        ],
        "pickups": [
            {
                "id": p["id"],
                "type": p["type"],
                "x": round(p["x"], 1),
                "y": round(p["y"], 1),
            }
            for p in room["pickups"]
        ],
        "weapons": {
            key: {
                "name": value["name"],
                "description": value["description"],
                "damage": value["damage"],
                "fire_rate": value["fire_rate"],
                "magazine": value["magazine"],
                "price": value["price"],
                "color": value["color"],
            }
            for key, value in WEAPONS.items()
        },
        "shop": SHOP_ITEMS,
        "obstacles": OBSTACLES,
    }


def broadcast(room):
    socketio.emit("state", get_state(room), room=room["code"])


# ============================================================================
# SOCKET EVENTS
# ============================================================================

@socketio.on("connect")
def connected():
    emit("connected", {"id": request.sid})


@socketio.on("create_room")
def create_room_event(data):
    data = data or {}
    mode = str(data.get("mode", "solo")).lower()
    name = clean_name(data.get("name", "Player"))

    with lock:
        room = create_room(mode)
        player = create_player(request.sid, name, 0)
        room["players"][request.sid] = player
        sid_room[request.sid] = room["code"]

    join_room(room["code"])
    emit("room_created", {
        "code": room["code"],
        "state": get_state(room),
    })


@socketio.on("join_room")
def join_room_event(data):
    data = data or {}
    code = str(data.get("code", "")).strip().upper()
    name = clean_name(data.get("name", "Player"))

    with lock:
        room = rooms.get(code)

        if room is None:
            emit("error_message", {"message": "Room not found."})
            return

        if room["started"]:
            emit("error_message", {"message": "That game has already started."})
            return

        if len(room["players"]) >= MAX_PLAYERS:
            emit("error_message", {"message": "That room is full."})
            return

        player = create_player(request.sid, name, len(room["players"]))
        room["players"][request.sid] = player
        sid_room[request.sid] = code

    join_room(code)
    emit("joined", {"code": code, "state": get_state(room)})
    broadcast(room)


@socketio.on("start_game")
def start_game_event():
    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)

        if not room:
            return

        if room["mode"] == "ffa" and len(room["players"]) < 3:
            emit("error_message", {"message": "FFA requires at least 3 players."})
            return

        if room["started"]:
            return

        room["started"] = True
        room["game_over"] = False
        room["wave"] = 0
        room["intermission"] = 0
        room["enemies"].clear()
        room["bullets"].clear()
        room["grenades"].clear()
        room["pickups"].clear()
        room["announcement"] = "GET READY"
        room["announcement_timer"] = 2.5

    broadcast(room)


@socketio.on("move")
def move_event(data):
    data = data or {}

    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        if not room:
            return

        player = room["players"].get(request.sid)
        if not player:
            return

        dx = clamp(safe_float(data.get("x")), -1, 1)
        dy = clamp(safe_float(data.get("y")), -1, 1)
        length = math.hypot(dx, dy)

        if length > 1:
            dx /= length
            dy /= length

        player["move_dx"] = dx
        player["move_dy"] = dy


@socketio.on("shoot")
def shoot_event(data):
    data = data or {}

    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        if not room:
            return

        player = room["players"].get(request.sid)
        if not player:
            return

        fire_weapon(room, player, safe_float(data.get("angle")))


@socketio.on("reload")
def reload_event():
    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        player = room["players"].get(request.sid) if room else None

        if player and player["alive"]:
            player["ammo"] = player["magazine"]


@socketio.on("dash")
def dash_event(data):
    data = data or {}

    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        player = room["players"].get(request.sid) if room else None

        if player:
            use_dash(player, safe_float(data.get("angle")))


@socketio.on("grenade")
def grenade_event(data):
    data = data or {}

    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        player = room["players"].get(request.sid) if room else None

        if player:
            use_grenade(
                room,
                player,
                safe_float(data.get("x"), player["x"]),
                safe_float(data.get("y"), player["y"]),
            )


@socketio.on("buy_item")
def buy_item_event(data):
    data = data or {}

    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        player = room["players"].get(request.sid) if room else None

        if not player:
            return

        ok, message = buy_item(player, str(data.get("item", "")))

    emit("purchase", {"success": ok, "message": message})


@socketio.on("buy_weapon")
def buy_weapon_event(data):
    data = data or {}

    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        player = room["players"].get(request.sid) if room else None

        if not player:
            return

        ok, message = buy_weapon(player, str(data.get("weapon", "")))

    emit("purchase", {"success": ok, "message": message})


@socketio.on("shop_toggle")
def shop_toggle_event(data):
    data = data or {}
    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        player = room["players"].get(request.sid) if room else None

        if not room or not player or not room["started"]:
            return

        # Shop pauses only SOLO. In CO-OP and FFA the world keeps moving.
        if room["mode"] == "solo":
            opening = bool(data.get("open"))
            room["paused"] = opening
            room["shop_paused_by"] = request.sid if opening else None


@socketio.on("leave_game")
def leave_game_event():
    with lock:
        code = sid_room.get(request.sid)
        if code and code in rooms:
            room = rooms[code]
            room["players"].pop(request.sid, None)
            sid_room.pop(request.sid, None)
            if not room["players"]:
                rooms.pop(code, None)
            else:
                broadcast_room(room)

@socketio.on("revive")
def revive_event(data):
    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        if not room:
            return

        player = room["players"].get(request.sid)
        if not player or player["alive"]:
            return

        # Reviving is available before the whole squad is permanently
        # eliminated. The price doubles for this player each time.
        cost = 1000 * (2 ** player.get("revives", 0))

        if player["coins"] < cost:
            socketio.emit("toast", {
                "message": f"You need {cost:,} coins to revive.",
                "kind": "error"
            }, to=request.sid)
            return

        player["coins"] -= cost
        player["revives"] = player.get("revives", 0) + 1
        player["alive"] = True
        player["health"] = player["max_health"]
        player["hit_flash"] = 0
        player["x"] = random.uniform(180, WORLD_W - 180)
        player["y"] = random.uniform(140, WORLD_H - 140)

        # Reviving any player means the squad is active again.
        room["squad_eliminated"] = False
        room["game_over"] = False

        socketio.emit("toast", {
            "message": f"{player['name']} revived for {cost:,} coins!",
            "kind": "success"
        }, room=code)

        broadcast_room(room)

@socketio.on("ffa_attack")
def ffa_attack_event(data):
    data = data or {}

    with lock:
        code = sid_room.get(request.sid)
        room = rooms.get(code)
        player = room["players"].get(request.sid) if room else None

        if player:
            ffa_attack(room, player, str(data.get("target", "")))


@socketio.on("disconnect")
def disconnected():
    with lock:
        code = sid_room.pop(request.sid, None)
        if not code:
            return

        room = rooms.get(code)
        if not room:
            return

        room["players"].pop(request.sid, None)
        if room.get("shop_paused_by") == request.sid:
            room["paused"] = False
            room["shop_paused_by"] = None

        if not room["players"]:
            rooms.pop(code, None)
            return

        if room["started"] and not any(p["alive"] for p in room["players"].values()):
            room["game_over"] = True

    broadcast(room)


# ============================================================================
# GAME LOOP
# ============================================================================

def update_room(room, dt):
    if not room["started"] or room["game_over"]:
        return
    if room.get("paused"):
        return

    room["announcement_timer"] = max(0.0, room["announcement_timer"] - dt)

    update_players(room, dt)
    update_wave_spawning(room, dt)
    update_enemies(room, dt)
    update_bullets(room, dt)
    update_grenades(room, dt)
    collect_pickups(room, dt)
    update_wave_progress(room, dt)

    if room["mode"] != "ffa":
        if room["players"] and not any(
            p["alive"] for p in room["players"].values()
        ):
            room["game_over"] = True
            room["announcement"] = "SQUAD ELIMINATED"
            room["announcement_timer"] = 999

    if room["mode"] == "ffa":
        alive = sum(1 for p in room["players"].values() if p["alive"])
        if len(room["players"]) >= 3 and alive <= 1:
            room["game_over"] = True
            room["announcement"] = "MATCH COMPLETE"
            room["announcement_timer"] = 999


def game_loop():
    previous = monotonic()
    state_accumulator = 0.0

    while True:
        current = monotonic()
        dt = min(0.1, current - previous)
        previous = current
        state_accumulator += dt

        with lock:
            active_rooms = list(rooms.values())

            for room in active_rooms:
                update_room(room, dt)

            # Clean abandoned rooms.
            for code, room in list(rooms.items()):
                if (
                    not room["players"]
                    and current - room["created"] > ROOM_CLEANUP_SECONDS
                ):
                    rooms.pop(code, None)

        if state_accumulator >= 1.0 / STATE_RATE:
            state_accumulator = 0.0
            with lock:
                for room in list(rooms.values()):
                    broadcast(room)

        socketio.sleep(1.0 / TICK_RATE)


# ============================================================================
# FRONTEND
# ============================================================================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Arena // Deluxe</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js">
document.getElementById("reviveBtn")?.addEventListener("click",()=>{
  socket.emit("revive",{});
});
document.getElementById("reviveWaitBtn")?.addEventListener("click",()=>{
  document.getElementById("reviveOverlay")?.classList.add("hidden");
});
document.getElementById("homeAfterWipe")?.addEventListener("click",()=>{
  socket.emit("leave_game",{});
  document.getElementById("eliminatedOverlay")?.classList.add("hidden");
  document.getElementById("game")?.classList.add("hidden");
  document.getElementById("home")?.classList.remove("hidden");
});

</script>
<style>
:root{
  --bg:#050810;
  --panel:rgba(10,17,30,.88);
  --panel2:rgba(16,28,47,.92);
  --line:rgba(104,150,196,.24);
  --text:#f4f8ff;
  --muted:#8ea4bf;
  --cyan:#55dfff;
  --blue:#5795ff;
  --green:#5ef29a;
  --yellow:#ffd45c;
  --red:#ff5c72;
  --purple:#b783ff;
  --shadow:0 24px 80px rgba(0,0,0,.48);
}
*{box-sizing:border-box}
html,body{
  margin:0;width:100%;height:100%;overflow:hidden;
  background:var(--bg);color:var(--text);
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif;
}
button,input{font:inherit}
button{cursor:pointer}
.hidden{display:none!important}

.screen{position:fixed;inset:0}
.center{display:flex;align-items:center;justify-content:center}

#menu{
  overflow:auto;
  background:
    radial-gradient(circle at 12% 20%,rgba(54,135,255,.20),transparent 32%),
    radial-gradient(circle at 84% 70%,rgba(121,61,255,.18),transparent 30%),
    linear-gradient(145deg,#03060c,#071221 55%,#050810);
}

.grid-bg{
  position:absolute;inset:0;opacity:.20;pointer-events:none;
  background-image:
    linear-gradient(rgba(105,160,210,.12) 1px,transparent 1px),
    linear-gradient(90deg,rgba(105,160,210,.12) 1px,transparent 1px);
  background-size:54px 54px;
  mask-image:linear-gradient(to bottom,black,transparent);
}

.menu-wrap{
  position:relative;
  width:min(1180px,94vw);
  display:grid;
  grid-template-columns:1.12fr .88fr;
  gap:18px;
  padding:30px 0;
}

.hero{
  padding:42px;
  min-height:620px;
  border:1px solid var(--line);
  border-radius:30px;
  background:
    linear-gradient(145deg,rgba(14,27,46,.92),rgba(5,10,19,.86));
  box-shadow:var(--shadow);
  overflow:hidden;
  position:relative;
}
.hero:after{
  content:"";
  position:absolute;
  width:420px;height:420px;
  right:-170px;top:-170px;
  border:1px solid rgba(85,223,255,.18);
  border-radius:50%;
  box-shadow:0 0 0 45px rgba(85,223,255,.025),
             0 0 0 90px rgba(85,223,255,.018);
}
.kicker{
  color:var(--cyan);font-size:12px;font-weight:900;
  letter-spacing:4px;text-transform:uppercase;
}
.logo{
  font-size:clamp(64px,8vw,112px);
  line-height:.78;
  letter-spacing:-7px;
  font-weight:1000;
  margin:20px 0;
  background:linear-gradient(135deg,#fff 5%,#66e4ff 44%,#7b76ff 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;
}
.hero p{
  max-width:620px;
  color:var(--muted);
  font-size:17px;line-height:1.65;
}
.feature-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:28px}
.feature{
  padding:10px 13px;border:1px solid var(--line);
  border-radius:999px;background:rgba(255,255,255,.035);
  color:#c5d4e8;font-size:12px;font-weight:800;
}
.card{
  border:1px solid var(--line);
  border-radius:30px;
  background:var(--panel);
  box-shadow:var(--shadow);
  padding:28px;
}
.card h2{margin:0 0 7px;font-size:27px}
.card .small{color:var(--muted);font-size:13px}

.label{
  display:block;margin:18px 0 7px;
  color:#9fb4cd;font-size:11px;
  font-weight:900;letter-spacing:1.5px;text-transform:uppercase;
}
input{
  width:100%;height:50px;padding:0 15px;
  border-radius:13px;border:1px solid var(--line);
  background:#050b14;color:white;outline:none;
}
input:focus{border-color:rgba(85,223,255,.7);box-shadow:0 0 0 3px rgba(85,223,255,.08)}

.mode{
  width:100%;display:flex;align-items:center;gap:14px;
  padding:15px;margin-top:10px;
  text-align:left;color:white;
  border:1px solid var(--line);border-radius:15px;
  background:rgba(255,255,255,.035);
  transition:.16s transform,.16s border-color,.16s background;
}
.mode:hover{
  transform:translateY(-2px);
  border-color:rgba(85,223,255,.55);
  background:rgba(85,223,255,.07);
}
.mode-icon{
  width:44px;height:44px;display:grid;place-items:center;
  border-radius:12px;background:rgba(85,223,255,.09);
  color:var(--cyan);font-size:20px;
}
.mode b{display:block;font-size:14px}
.mode span{display:block;color:var(--muted);font-size:12px;margin-top:3px}
.join-row{display:grid;grid-template-columns:1fr auto;gap:9px;margin-top:9px}

.btn{
  border:0;border-radius:12px;padding:12px 16px;
  color:#fff;font-weight:900;
}
.btn-primary{
  background:linear-gradient(135deg,#2c9fdf,#5b70ff);
  box-shadow:0 9px 28px rgba(50,130,255,.22);
}
.btn-dark{background:#101c2e;border:1px solid var(--line)}
.btn-danger{background:#6e2635}
.btn-green{background:#187f57}
.btn:disabled{opacity:.45;cursor:not-allowed}

#error{color:#ff788b;font-size:12px;min-height:18px;margin-top:8px}

#lobby{
  background:
    radial-gradient(circle at 50% 20%,rgba(65,138,255,.12),transparent 40%),
    #050910;
}
.lobby-box{width:min(620px,94vw)}
.room-code{
  margin:22px 0;
  text-align:center;
  font-size:54px;font-weight:1000;
  letter-spacing:12px;
  color:var(--cyan);
  text-shadow:0 0 32px rgba(85,223,255,.25);
}
.lobby-list{
  border:1px solid var(--line);
  border-radius:16px;overflow:hidden;
  margin:16px 0;
}
.lobby-player{
  display:flex;justify-content:space-between;align-items:center;
  padding:13px 15px;background:rgba(255,255,255,.025);
  border-bottom:1px solid var(--line);
}
.lobby-player:last-child{border-bottom:0}
.status-dot{
  display:inline-block;width:7px;height:7px;border-radius:50%;
  background:var(--green);box-shadow:0 0 10px var(--green);
  margin-right:7px;
}

#game{background:#02050a}
#canvas{position:absolute;inset:0;width:100%;height:100%;cursor:crosshair}

.topbar{
  position:absolute;left:14px;right:14px;top:14px;
  display:flex;justify-content:space-between;gap:12px;
  pointer-events:none;
}
.hud-card{
  pointer-events:auto;
  border:1px solid var(--line);
  background:rgba(5,12,22,.86);
  backdrop-filter:blur(14px);
  box-shadow:0 14px 45px rgba(0,0,0,.28);
  border-radius:17px;padding:12px 14px;
}
.player-hud{min-width:280px}
.hud-name{font-weight:1000;font-size:15px}
.hud-sub{font-size:11px;color:var(--muted);margin-top:2px}
.bar{
  height:9px;border-radius:99px;background:#1a2636;
  overflow:hidden;margin:9px 0 6px;
}
.bar > div{height:100%;border-radius:99px;transition:width .18s}
.hp-fill{background:linear-gradient(90deg,#38d879,#91f79e)}
.xp-fill{background:linear-gradient(90deg,#6d78ff,#c27cff)}
.hud-stats{display:flex;gap:14px;font-size:12px;color:#b9c9dc}
.hud-stats b{color:white}

.center-info{
  position:absolute;top:14px;left:50%;
  transform:translateX(-50%);
  text-align:center;pointer-events:none;
}
.wave-pill{
  padding:8px 14px;border-radius:99px;
  background:rgba(5,12,22,.88);
  border:1px solid var(--line);
  font-size:12px;font-weight:1000;letter-spacing:1.5px;
}
.announcement{
  margin-top:12px;
  font-size:38px;font-weight:1000;
  letter-spacing:2px;
  text-shadow:0 5px 30px rgba(0,0,0,.8);
  opacity:0;
  transform:translateY(-8px);
  transition:.2s;
}
.announcement.show{opacity:1;transform:translateY(0)}

.right-hud{min-width:230px;text-align:right}
.score{font-size:22px;font-weight:1000}
.combo{color:var(--yellow);font-weight:900;font-size:12px}

#leaderboard{
  position:absolute;right:14px;top:102px;width:235px;
  border:1px solid var(--line);
  background:rgba(5,12,22,.80);
  backdrop-filter:blur(12px);
  border-radius:15px;padding:10px;
}
.lb-title{
  font-size:10px;font-weight:1000;letter-spacing:2px;
  color:#8da5bf;margin-bottom:7px;
}
.lb-row{
  display:flex;justify-content:space-between;
  padding:7px 6px;border-radius:8px;font-size:11px;
}
.lb-row.me{background:rgba(85,223,255,.09);color:var(--cyan)}
.lb-row.dead{opacity:.4}

.bottom-hud{
  position:absolute;left:14px;right:14px;bottom:14px;
  display:flex;justify-content:space-between;align-items:end;
  pointer-events:none;
}
.weapon-card,.ability-card,.help-card{
  pointer-events:auto;
  border:1px solid var(--line);
  background:rgba(5,12,22,.86);
  backdrop-filter:blur(12px);
  border-radius:15px;padding:11px 13px;
}
.weapon-name{font-weight:1000;font-size:14px}
.ammo{font-size:27px;font-weight:1000;margin-top:2px}
.ammo small{font-size:12px;color:var(--muted)}
.ability-row{display:flex;gap:8px}
.ability{
  min-width:90px;text-align:center;
  border:1px solid var(--line);border-radius:12px;
  background:rgba(255,255,255,.035);padding:8px 10px;
}
.ability b{display:block;font-size:11px}
.ability span{font-size:10px;color:var(--muted)}
.help-card{font-size:10px;color:#8da2bb;line-height:1.55;text-align:right}

#shop{
  position:absolute;inset:0;z-index:30;
  display:flex;align-items:center;justify-content:center;
  background:rgba(1,4,9,.80);
  backdrop-filter:blur(8px);
}
.shop-window{
  width:min(1040px,94vw);max-height:90vh;overflow:hidden;
  border:1px solid rgba(110,170,225,.28);
  border-radius:24px;background:#08111e;
  box-shadow:0 40px 120px rgba(0,0,0,.65);
  display:flex;flex-direction:column;
}
.shop-header{
  padding:19px 22px;border-bottom:1px solid var(--line);
  display:flex;align-items:center;justify-content:space-between;
}
.shop-header h2{margin:0;font-size:24px}
.shop-money{color:var(--yellow);font-weight:1000}
.tabs{display:flex;gap:7px}
.tab{
  padding:8px 11px;border:1px solid var(--line);
  border-radius:9px;background:#0d1a2c;color:#9eb3cb;
}
.tab.active{color:white;border-color:rgba(85,223,255,.55);background:rgba(85,223,255,.09)}
.shop-body{padding:18px;overflow:auto}
.shop-grid{
  display:grid;grid-template-columns:repeat(3,1fr);gap:11px;
}
.shop-item{
  border:1px solid var(--line);border-radius:16px;
  padding:15px;background:linear-gradient(145deg,#0d1b2d,#0a1422);
  position:relative;overflow:hidden;
}
.shop-item:before{
  content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
  background:var(--cyan);opacity:.65;
}
.shop-icon{
  width:38px;height:38px;border-radius:10px;
  display:grid;place-items:center;
  background:rgba(85,223,255,.08);color:var(--cyan);
  font-weight:1000;font-size:18px;
}
.shop-item h3{margin:11px 0 4px;font-size:14px}
.shop-item p{min-height:37px;margin:0 0 12px;color:var(--muted);font-size:11px;line-height:1.45}
.shop-buy{
  width:100%;padding:9px;border-radius:9px;
  border:1px solid var(--line);background:#102039;color:white;
  font-weight:900;font-size:11px;
}
.shop-buy:hover{border-color:rgba(85,223,255,.5);background:#132b47}

#downed{
  position:absolute;inset:0;z-index:20;
  display:flex;align-items:center;justify-content:center;
  background:rgba(20,0,8,.22);
  pointer-events:none;
}
.downed-card{
  pointer-events:auto;text-align:center;
  padding:30px 38px;border-radius:22px;
  background:rgba(10,10,17,.93);
  border:1px solid rgba(255,92,114,.38);
  box-shadow:0 30px 90px rgba(0,0,0,.6);
}
.downed-card h1{margin:0;color:#ff687b;font-size:42px}
.downed-card p{color:var(--muted);font-size:13px}

#toast{
  position:absolute;left:50%;bottom:120px;
  transform:translateX(-50%) translateY(15px);
  opacity:0;pointer-events:none;
  background:#0a1727;border:1px solid var(--line);
  padding:10px 15px;border-radius:99px;
  color:white;font-size:12px;font-weight:800;
  transition:.2s;z-index:50;
}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

@media(max-width:900px){
  .menu-wrap{grid-template-columns:1fr}
  .hero{min-height:auto;padding:28px}
  .logo{font-size:72px}
  .shop-grid{grid-template-columns:repeat(2,1fr)}
  #leaderboard{width:190px}
  .help-card{display:none}
}
@media(max-width:600px){
  .topbar{gap:6px}.player-hud{min-width:0;width:190px}
  .right-hud{min-width:130px}
  .hud-stats{gap:7px}
  .player-hud .hud-sub{display:none}
  #leaderboard{top:91px;width:160px}
  .shop-grid{grid-template-columns:1fr}
  .shop-header{flex-wrap:wrap;gap:10px}
  .bottom-hud{left:7px;right:7px;bottom:7px}
  .ability-card{display:none}
}

#reviveOverlay,#eliminatedOverlay{
  position:fixed;inset:0;z-index:80;display:flex;align-items:center;
  justify-content:center;background:rgba(1,4,9,.82);backdrop-filter:blur(9px);
}
#reviveOverlay.hidden,#eliminatedOverlay.hidden{display:none}
.revive-card,.eliminated-card{
  width:min(480px,90vw);padding:34px;border:1px solid rgba(105,190,255,.25);
  border-radius:22px;background:linear-gradient(180deg,rgba(13,25,40,.98),rgba(5,11,19,.98));
  box-shadow:0 30px 90px rgba(0,0,0,.65);text-align:center;
}
.revive-card h2,.eliminated-card h2{font-size:32px;margin:0 0 8px}
.revive-cost{font-size:26px;font-weight:900;margin:18px 0}
.revive-sub{color:#9eb2c6;margin-bottom:22px}
.big-action{
  width:100%;padding:14px 18px;border:0;border-radius:12px;
  font:900 15px Arial;cursor:pointer;background:#55dfff;color:#04101a;
}
.big-action.secondary{margin-top:10px;background:#172738;color:#dbeaff}
.big-action:disabled{opacity:.45;cursor:not-allowed}

</style>
</head>
<body>

<!-- MENU -->
<div id="menu" class="screen center">
  <div class="grid-bg"></div>
  <div class="menu-wrap">
    <section class="hero">
      <div class="kicker">DELUXE COMBAT SIMULATION</div>
      <div class="logo">BOT<br>ARENA</div>
      <p>
        Survive escalating waves of hostile machines. Build your loadout,
        level up, chain kills for bigger rewards, use your dash and grenades,
        and push as far as you can.
      </p>
      <div class="feature-row">
        <div class="feature">⚔ HARDER WAVES</div>
        <div class="feature">★ ELITES</div>
        <div class="feature">☠ BOSS WAVES</div>
        <div class="feature">ϟ ABILITIES</div>
        <div class="feature">⬢ LOOT DROPS</div>
        <div class="feature">⌁ MULTIPLAYER</div>
      </div>
    </section>

    <section class="card">
      <h2>DEPLOY</h2>
      <div class="small">Choose a callsign, then select your mission.</div>

      <label class="label">CallsSign</label>
      <input id="name" maxlength="18" placeholder="Player" autocomplete="off">

      <button class="mode" onclick="createGame('solo')">
        <div class="mode-icon">◉</div>
        <div><b>SOLO // SURVIVAL</b><span>Fight the entire machine army yourself.</span></div>
      </button>

      <button class="mode" onclick="createGame('multiplayer')">
        <div class="mode-icon">⌘</div>
        <div><b>CO-OP // FIRETEAM</b><span>Join forces and survive escalating waves.</span></div>
      </button>

      <button class="mode" onclick="createGame('ffa')">
        <div class="mode-icon">⚔</div>
        <div><b>FFA // LAST STANDING</b><span>3–8 players. Eliminate the competition.</span></div>
      </button>

      <label class="label">Join existing room</label>
      <div class="join-row">
        <input id="joinCode" maxlength="6" placeholder="ROOM CODE" autocomplete="off">
        <button class="btn btn-primary" onclick="joinGame()">JOIN</button>
      </div>
      <div id="error"></div>
    </section>
  </div>
</div>

<!-- LOBBY -->
<div id="lobby" class="screen center hidden">
  <div class="card lobby-box">
    <div class="kicker">FIRETEAM LOBBY</div>
    <h2 id="lobbyMode">MISSION</h2>
    <div class="room-code" id="roomCode">------</div>
    <div class="small" style="text-align:center">Share this code with your squad.</div>

    <div class="lobby-list" id="lobbyPlayers"></div>

    <div style="display:flex;gap:8px">
      <button class="btn btn-primary" style="flex:1" onclick="startGame()">DEPLOY</button>
      <button class="btn btn-dark" onclick="location.reload()">LEAVE</button>
    </div>
  </div>
</div>

<!-- GAME -->
<div id="game" class="screen hidden">
  <canvas id="canvas"></canvas>

  <div class="topbar">
    <div class="hud-card player-hud">
      <div class="hud-name" id="playerName">PLAYER</div>
      <div class="hud-sub">LEVEL <b id="level">1</b> · <span id="weapon">PULSE PISTOL</span></div>
      <div class="bar"><div class="hp-fill" id="healthBar"></div></div>
      <div class="hud-stats">
        <span>HP <b id="healthText">110/110</b></span>
        <span>🪙 <b id="coins">450</b></span>
      </div>
      <div class="bar" style="height:4px;margin-bottom:0"><div class="xp-fill" id="xpBar"></div></div>
    </div>

    <div class="center-info">
      <div class="wave-pill">
        WAVE <span id="wave">0</span>
        <span style="color:#617890"> · </span>
        REMAINING <span id="remaining">0</span>
      </div>
      <div class="announcement" id="announcement">GET READY</div>
    </div>

    <div class="hud-card right-hud">
      <div class="hud-sub">TOTAL SCORE</div>
      <div class="score" id="score">0</div>
      <div class="combo" id="combo">COMBO ×0</div>
    </div>
  </div>

  <div id="leaderboard"></div>

  <div class="bottom-hud">
    <div class="weapon-card">
      <div class="weapon-name" id="weaponBottom">PULSE PISTOL</div>
      <div class="ammo"><span id="ammo">14</span><small> / <span id="mag">14</span></small></div>
    </div>

    <div class="ability-card">
      <div class="ability-row">
        <div class="ability"><b>SPACE</b><span id="dashText">DASH READY</span></div>
        <div class="ability"><b>G</b><span id="grenadeText">GRENADES 2</span></div>
        <div class="ability"><b>B</b><span>OPEN SHOP</span></div>
      </div>
    </div>

    <div class="help-card">
      WASD MOVE · MOUSE AIM<br>
      CLICK FIRE · R RELOAD · SPACE DASH<br>
      G THROW GRENADE · B SHOP
    </div>
  </div>

  <div id="toast"></div>

  <div id="downed" class="hidden">
    <div class="downed-card">
      <h1>DOWNED</h1>
      <p>Spend coins to get back into the fight.</p>
      <button class="btn btn-primary" onclick="revive()">REVIVE <span id="reviveCost">500</span> 🪙</button>
    </div>
  </div>

  <div id="shop" class="hidden">
    <div class="shop-window">
      <div class="shop-header">
        <div>
          <h2>ARMORY</h2>
          <div class="small">Upgrade before the next wave.</div>
        </div>
        <div class="tabs">
          <button class="tab active" id="tabUpgrades" onclick="renderShop('upgrades')">UPGRADES</button>
          <button class="tab" id="tabWeapons" onclick="renderShop('weapons')">WEAPONS</button>
          <button class="btn btn-dark" onclick="closeShop()">ESC</button>
        </div>
        <div class="shop-money">🪙 <span id="shopMoney">0</span></div>
      </div>
      <div class="shop-body">
        <div id="shopItems" class="shop-grid"></div>
      </div>
    </div>
  </div>
</div>

<script>
const socket = io();
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

let state = null;
let myId = null;
let mouse = {x:0,y:0,down:false};
let keys = Object.create(null);
let lastShot = 0;
let shopTab = "upgrades";
let toastTimer = null;

const WORLD_W = 1600;
const WORLD_H = 900;

const COLORS = {
  cyan:"#55dfff",
  blue:"#5795ff",
  green:"#5ef29a",
  red:"#ff5c72",
  yellow:"#ffd45c",
  purple:"#b783ff"
};

function resize(){
  canvas.width = innerWidth * devicePixelRatio;
  canvas.height = innerHeight * devicePixelRatio;
  canvas.style.width = innerWidth+"px";
  canvas.style.height = innerHeight+"px";
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
}
addEventListener("resize",resize);
resize();

function show(id){
  ["menu","lobby","game"].forEach(x=>document.getElementById(x).classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}

function nameValue(){
  return document.getElementById("name").value.trim() || "Player";
}

function createGame(mode){
  document.getElementById("error").textContent="";
  socket.emit("create_room",{mode,name:nameValue()});
}

function joinGame(){
  document.getElementById("error").textContent="";
  socket.emit("join_room",{
    code:document.getElementById("joinCode").value.trim().toUpperCase(),
    name:nameValue()
  });
}

function startGame(){socket.emit("start_game")}

socket.on("connect",()=>myId=socket.id);
socket.on("connected",d=>myId=d.id);

socket.on("room_created",d=>{
  myId=socket.id;
  state=d.state;
  document.getElementById("roomCode").textContent=d.code;
  show("lobby");
  updateLobby();
});

socket.on("joined",d=>{
  myId=socket.id;
  state=d.state;
  document.getElementById("roomCode").textContent=d.code;
  show("lobby");
  updateLobby();
});

socket.on("error_message",d=>{
  document.getElementById("error").textContent=d.message||"Something went wrong.";
});

socket.on("purchase",d=>{
  toast(d.message);
  if(!document.getElementById("shop").classList.contains("hidden"))renderShop(shopTab);
});

socket.on("revive_result",d=>{
  toast(d.message);
});

socket.on("state",d=>{
  state=d;
  if(d.started)show("game");
  else{
    show("lobby");
    updateLobby();
  }
  updateHUD();
});

function updateLobby(){
  if(!state)return;
  document.getElementById("lobbyMode").textContent=state.mode_name;
  document.getElementById("lobbyPlayers").innerHTML=state.players.map(p=>`
    <div class="lobby-player">
      <span><i class="status-dot"></i>${esc(p.name)}</span>
      <span style="color:#7e94ad;font-size:11px">${p.alive?"READY":"DOWN"}</span>
    </div>`).join("");
}

function updateHUD(){
  if(!state)return;

  document.getElementById("wave").textContent=state.wave;
  const pauseBadge=document.getElementById("pauseBadge");
  if(pauseBadge)pauseBadge.style.display=state.paused?"inline":"none";
  document.getElementById("score").textContent=state.score;
  document.getElementById("remaining").textContent=state.enemies.length+state.spawn_left;

  const me=state.players.find(p=>p.id===myId);
  if(!me)return;

  document.getElementById("playerName").textContent=me.name;
  document.getElementById("level").textContent=me.level;
  document.getElementById("coins").textContent=me.coins;
  document.getElementById("healthText").textContent=`${me.health}/${me.max_health}`;
  document.getElementById("healthBar").style.width=
    Math.max(0,Math.min(100,me.health/me.max_health*100))+"%";
  document.getElementById("xpBar").style.width=
    Math.max(0,Math.min(100,me.xp/me.xp_needed*100))+"%";

  const weapon=state.weapons[me.weapon];
  const weaponName=weapon?weapon.name.toUpperCase():me.weapon.toUpperCase();
  document.getElementById("weapon").textContent=weaponName;
  document.getElementById("weaponBottom").textContent=weaponName;
  document.getElementById("ammo").textContent=me.ammo;
  document.getElementById("mag").textContent=me.magazine;

  document.getElementById("combo").textContent=`COMBO ×${me.combo}`;
  document.getElementById("dashText").textContent=
    me.dash_cd<=0?"DASH READY":`COOLDOWN ${me.dash_cd}s`;
  document.getElementById("grenadeText").textContent=`GRENADES ${me.grenades}`;
  document.getElementById("shopMoney").textContent=me.coins;
  document.getElementById("reviveCost").textContent=me.revive_cost;

  document.getElementById("downed").classList.toggle("hidden",me.alive||state.game_over);

  const ann=document.getElementById("announcement");
  ann.textContent=state.announcement||"";
  ann.classList.toggle("show",state.announcement_timer>0);

  updateLeaderboard();
}

function updateLeaderboard(){
  const board=document.getElementById("leaderboard");
  const sorted=[...state.players].sort((a,b)=>b.score-a.score);
  board.innerHTML=`
    <div class="lb-title">${state.mode==="ffa"?"PLAYERS":"FIRETEAM"}</div>
    ${sorted.map((p,i)=>`
      <div class="lb-row ${p.id===myId?"me ":""}${p.alive?"":"dead"}">
        <span>${i+1}. ${esc(p.name)}</span>
        <span>${p.score}</span>
      </div>`).join("")}`;
}

function esc(s){
  return String(s).replace(/[&<>"']/g,c=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[c]));
}

function toast(text){
  const el=document.getElementById("toast");
  el.textContent=text;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>el.classList.remove("show"),1800);
}

function camera(){
  const scale=Math.min(innerWidth/WORLD_W,innerHeight/WORLD_H);
  return {
    scale,
    ox:(innerWidth-WORLD_W*scale)/2,
    oy:(innerHeight-WORLD_H*scale)/2
  };
}

function worldPoint(){
  const c=camera();
  return {
    x:(mouse.x-c.ox)/c.scale,
    y:(mouse.y-c.oy)/c.scale
  };
}

function aimAngle(){
  const me=state?.players.find(p=>p.id===myId);
  if(!me)return 0;
  const p=worldPoint();
  return Math.atan2(p.y-me.y,p.x-me.x);
}

function shoot(){
  if(!state?.started)return;
  if(!document.getElementById("shop").classList.contains("hidden") && state.mode==="solo")return;
  const me=state.players.find(p=>p.id===myId);
  if(!me?.alive)return;
  const t=performance.now();
  if(t-lastShot<22)return;
  lastShot=t;
  socket.emit("shoot",{angle:aimAngle()});
}

function dash(){
  if(!state)return;
  if(!document.getElementById("shop").classList.contains("hidden") && state.mode==="solo")return;
  socket.emit("dash",{angle:aimAngle()});
}

function throwGrenade(){
  if(!state)return;
  if(!document.getElementById("shop").classList.contains("hidden") && state.mode==="solo")return;
  const p=worldPoint();
  socket.emit("grenade",{x:p.x,y:p.y});
}

canvas.addEventListener("mousemove",e=>{
  const r=canvas.getBoundingClientRect();
  mouse.x=e.clientX-r.left;
  mouse.y=e.clientY-r.top;
});
canvas.addEventListener("mousedown",e=>{
  if(e.button===0){
    mouse.down=true;
    shoot();
  }
});
addEventListener("mouseup",e=>{
  if(e.button===0)mouse.down=false;
});

addEventListener("keydown",e=>{
  const k=e.key.toLowerCase();
  keys[k]=true;

  if(k==="r")socket.emit("reload");
  if(k==="b")openShop();
  if(k==="escape" && !document.getElementById("shop").classList.contains("hidden"))closeShop();
  if(k===" "){
    e.preventDefault();
    dash();
  }
  if(k==="g")throwGrenade();

  if(k==="e"){
    const me=state?.players.find(p=>p.id===myId);
    if(me&&!me.alive)revive();
  }
});

addEventListener("keyup",e=>keys[e.key.toLowerCase()]=false);
addEventListener("beforeunload",()=>socket.emit("shop_toggle",{open:false}));

setInterval(()=>{
  let dx=0,dy=0;
  if(keys.w)dy--;
  if(keys.s)dy++;
  if(keys.a)dx--;
  if(keys.d)dx++;
  socket.emit("move",{x:dx,y:dy});
  if(mouse.down)shoot();
},50);

function openShop(){
  if(!state)return;
  const me=state.players?.find(p=>p.id===myId);
  if(!me?.alive)return;
  document.getElementById("shop").classList.remove("hidden");
  renderShop(shopTab);
  socket.emit("shop_toggle",{open:true});
}

function closeShop(){
  document.getElementById("shop").classList.add("hidden");
  socket.emit("shop_toggle",{open:false});
}

function renderShop(tab){
  shopTab=tab;
  document.getElementById("tabUpgrades").classList.toggle("active",tab==="upgrades");
  document.getElementById("tabWeapons").classList.toggle("active",tab==="weapons");

  const box=document.getElementById("shopItems");
  const me=state.players.find(p=>p.id===myId);
  if(!me)return;

  if(tab==="weapons"){
    box.innerHTML=Object.entries(state.weapons).map(([id,w])=>{
      const owned=me.owned_weapons.includes(id);
      const current=me.weapon===id;
      return `
        <div class="shop-item">
          <div class="shop-icon" style="color:${w.color}">◈</div>
          <h3>${esc(w.name)}</h3>
          <p>${esc(w.description)}<br>
             Damage ${w.damage} · ${w.fire_rate}/s · ${w.magazine} mag</p>
          <button class="shop-buy" onclick="buyWeapon('${id}')">
            ${current?"EQUIPPED":owned?"EQUIP":"BUY — "+w.price+" 🪙"}
          </button>
        </div>`;
    }).join("");
    return;
  }

  box.innerHTML=Object.entries(state.shop).map(([id,item])=>`
    <div class="shop-item">
      <div class="shop-icon">${esc(item.icon)}</div>
      <h3>${esc(item.name)}</h3>
      <p>${esc(item.description)}</p>
      <button class="shop-buy" onclick="buyItem('${id}')">
        BUY — ${item.price} 🪙
      </button>
    </div>`).join("");
}

function buyItem(id){socket.emit("buy_item",{item:id})}
function buyWeapon(id){socket.emit("buy_weapon",{weapon:id})}
function revive(){socket.emit("revive")}

function roundedRectPath(ctx,x,y,w,h,r){
  const rr=Math.min(r,w/2,h/2);
  ctx.beginPath();
  ctx.moveTo(x+rr,y);
  ctx.arcTo(x+w,y,x+w,y+h,rr);
  ctx.arcTo(x+w,y+h,x,y+h,rr);
  ctx.arcTo(x,y+h,x,y,rr);
  ctx.arcTo(x,y,x+w,y,rr);
  ctx.closePath();
}

function drawGlowCircle(x,y,r,color,alpha=.25){
  ctx.save();
  ctx.globalAlpha=alpha;
  ctx.fillStyle=color;
  ctx.shadowBlur=r*2.2;
  ctx.shadowColor=color;
  ctx.beginPath();
  ctx.arc(x,y,r,0,Math.PI*2);
  ctx.fill();
  ctx.restore();
}

function drawArena(){
  const c=camera();
  ctx.save();
  ctx.translate(c.ox,c.oy);
  ctx.scale(c.scale,c.scale);

  // Deep arena background.
  const bg=ctx.createLinearGradient(0,0,0,WORLD_H);
  bg.addColorStop(0,"#07101c");
  bg.addColorStop(.52,"#040a13");
  bg.addColorStop(1,"#02060c");
  ctx.fillStyle=bg;
  ctx.fillRect(0,0,WORLD_W,WORLD_H);

  // Large ambient lights.
  drawGlowCircle(800,450,210,"#1c8dcc",.045);
  drawGlowCircle(220,140,170,"#6a58ff",.025);
  drawGlowCircle(1380,760,210,"#ff4f83",.018);

  // Floor grid with stronger major lines.
  ctx.lineWidth=1;
  for(let x=0;x<=WORLD_W;x+=50){
    ctx.strokeStyle=(x%250===0)?"rgba(110,180,220,.13)":"rgba(76,133,177,.055)";
    ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,WORLD_H);ctx.stroke();
  }
  for(let y=0;y<=WORLD_H;y+=50){
    ctx.strokeStyle=(y%250===0)?"rgba(110,180,220,.13)":"rgba(76,133,177,.055)";
    ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(WORLD_W,y);ctx.stroke();
  }

  // Decorative arena lanes.
  ctx.strokeStyle="rgba(85,223,255,.055)";
  ctx.lineWidth=2;
  for(let x=100;x<WORLD_W;x+=300){
    ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,WORLD_H);ctx.stroke();
  }

  // Arena boundary.
  ctx.strokeStyle="rgba(85,223,255,.34)";
  ctx.lineWidth=4;
  ctx.strokeRect(3,3,WORLD_W-6,WORLD_H-6);
  ctx.strokeStyle="rgba(85,223,255,.08)";
  ctx.lineWidth=14;
  ctx.strokeRect(10,10,WORLD_W-20,WORLD_H-20);

  // Obstacles become actual sci-fi structures.
  for(const r of state.obstacles||[]){
    ctx.save();
    ctx.shadowBlur=20;
    ctx.shadowColor="rgba(0,0,0,.7)";
    ctx.fillStyle="#091523";
    roundedRectPath(ctx,r.x,r.y,r.w,r.h,10);
    ctx.fill();
    ctx.shadowBlur=0;

    ctx.strokeStyle="rgba(110,170,220,.28)";
    ctx.lineWidth=2;
    roundedRectPath(ctx,r.x,r.y,r.w,r.h,10);
    ctx.stroke();

    ctx.fillStyle="rgba(85,223,255,.045)";
    roundedRectPath(ctx,r.x+7,r.y+7,r.w-14,r.h-14,7);
    ctx.fill();

    ctx.strokeStyle="rgba(85,223,255,.13)";
    ctx.lineWidth=1;
    for(let xx=r.x+20;xx<r.x+r.w-10;xx+=34){
      ctx.beginPath();ctx.moveTo(xx,r.y+8);ctx.lineTo(xx,r.y+r.h-8);ctx.stroke();
    }

    ctx.fillStyle="#14273a";
    for(const [px,py] of [[r.x+12,r.y+12],[r.x+r.w-12,r.y+12],
                          [r.x+12,r.y+r.h-12],[r.x+r.w-12,r.y+r.h-12]]){
      ctx.beginPath();ctx.arc(px,py,3,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

  // Pickups: proper holographic objects rather than dots.
  for(const p of state.pickups){
    const pulse=1+Math.sin(performance.now()/180+p.x)*.08;
    const colors={coin:"#ffd45c",heal:"#5ef29a",ammo:"#55dfff",energy:"#b783ff"};
    const col=colors[p.type]||"#fff";
    drawGlowCircle(p.x,p.y,11,col,.16);

    ctx.save();
    ctx.translate(p.x,p.y);
    ctx.rotate(performance.now()/1100);
    ctx.strokeStyle=col;
    ctx.fillStyle="rgba(8,18,30,.92)";
    ctx.lineWidth=2;
    ctx.shadowBlur=14;
    ctx.shadowColor=col;

    if(p.type==="coin"){
      ctx.beginPath();ctx.arc(0,0,9*pulse,0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.fillStyle=col;ctx.font="900 10px Arial";ctx.textAlign="center";
      ctx.fillText("¢",0,3);
    }else if(p.type==="heal"){
      ctx.beginPath();ctx.moveTo(-5,-10);ctx.lineTo(5,-10);ctx.lineTo(5,-3);
      ctx.lineTo(10,-3);ctx.lineTo(10,5);ctx.lineTo(5,5);ctx.lineTo(5,10);
      ctx.lineTo(-5,10);ctx.lineTo(-5,5);ctx.lineTo(-10,5);ctx.lineTo(-10,-3);
      ctx.lineTo(-5,-3);ctx.closePath();ctx.fill();ctx.stroke();
      ctx.fillStyle=col;ctx.fillRect(-2, -7,4,14);ctx.fillRect(-7,-2,14,4);
    }else if(p.type==="ammo"){
      roundedRectPath(ctx,-8,-10,16,20,3);ctx.fill();ctx.stroke();
      ctx.fillStyle=col;ctx.fillRect(-4,-6,8,2);ctx.fillRect(-4,-1,8,2);ctx.fillRect(-4,4,8,2);
    }else{
      ctx.beginPath();ctx.moveTo(0,-11);ctx.lineTo(8,-2);ctx.lineTo(3,10);
      ctx.lineTo(-3,10);ctx.lineTo(-8,-2);ctx.closePath();ctx.fill();ctx.stroke();
      ctx.fillStyle=col;ctx.beginPath();ctx.arc(0,0,3,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

  // Grenades / blast previews.
  for(const g of state.grenades){
    const progress=1-g.timer/.65;
    ctx.save();
    ctx.strokeStyle=`rgba(255,120,90,${.35+.5*progress})`;
    ctx.lineWidth=3;
    ctx.setLineDash([9,7]);
    ctx.beginPath();ctx.arc(g.x,g.y,g.radius*progress,0,Math.PI*2);ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle="#ff7b61";
    ctx.shadowBlur=18;ctx.shadowColor="#ff7b61";
    ctx.beginPath();ctx.arc(g.x,g.y,8,0,Math.PI*2);ctx.fill();
    ctx.restore();
  }

  // Projectiles are directional streaks.
  for(const b of state.bullets){
    const ang=Math.atan2(b.dy||0,b.dx||1);
    const len=b.enemy?17:22;
    const col=b.enemy?"#ff5e75":"#eaf9ff";
    ctx.save();
    ctx.translate(b.x,b.y);ctx.rotate(ang);
    ctx.strokeStyle=col;ctx.lineWidth=b.enemy?4:3;
    ctx.shadowBlur=12;ctx.shadowColor=col;
    ctx.beginPath();ctx.moveTo(-len,0);ctx.lineTo(len,0);ctx.stroke();
    ctx.fillStyle=col;ctx.beginPath();ctx.arc(len,0,b.enemy?3:2.5,0,Math.PI*2);ctx.fill();
    ctx.restore();
  }

  // ---------------- ENEMIES ----------------
  for(const e of state.enemies){
    const t=performance.now()/1000;
    const bob=Math.sin(t*4+e.x*.01)*1.5;
    const flash=e.hit_flash;
    let col="#ff586f";
    if(e.type==="runner")col="#ffd45c";
    if(e.type==="brute")col="#ef6877";
    if(e.type==="sniper")col="#bd83ff";
    if(e.type==="tank")col="#e28a52";
    if(e.type==="boss")col="#d84cff";
    if(e.elite)col="#fff17a";

    ctx.save();
    ctx.translate(e.x,e.y+bob);

    // Ground shadow.
    ctx.fillStyle="rgba(0,0,0,.38)";
    ctx.beginPath();ctx.ellipse(0,e.radius*.78,e.radius*1.15,e.radius*.34,0,0,Math.PI*2);ctx.fill();

    ctx.shadowBlur=(e.elite||e.type==="boss")?28:12;
    ctx.shadowColor=col;

    if(e.type==="drone"){
      // Four-legged scout bot.
      ctx.strokeStyle=col;ctx.lineWidth=5;
      for(const side of [-1,1]){
        ctx.beginPath();ctx.moveTo(side*8,4);ctx.lineTo(side*19,15);ctx.lineTo(side*25,7);ctx.stroke();
        ctx.beginPath();ctx.moveTo(side*9,-3);ctx.lineTo(side*21,-15);ctx.lineTo(side*25,-7);ctx.stroke();
      }
      ctx.fillStyle="#101b29";ctx.strokeStyle=col;ctx.lineWidth=3;
      ctx.beginPath();ctx.ellipse(0,0,19,14,0,0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.fillStyle=flash?"#fff":col;
      ctx.beginPath();ctx.arc(4,0,6,0,Math.PI*2);ctx.fill();
      ctx.fillStyle="#dffaff";ctx.beginPath();ctx.arc(6,-2,2,0,Math.PI*2);ctx.fill();
    }else if(e.type==="runner"){
      // Sleek quadruped.
      ctx.strokeStyle=col;ctx.lineWidth=5;
      for(const sx of [-1,1]){
        ctx.beginPath();ctx.moveTo(sx*7,5);ctx.lineTo(sx*17,18);ctx.lineTo(sx*25,15);ctx.stroke();
        ctx.beginPath();ctx.moveTo(sx*8,-4);ctx.lineTo(sx*18,-17);ctx.lineTo(sx*25,-13);ctx.stroke();
      }
      ctx.fillStyle="#131b25";ctx.strokeStyle=col;ctx.lineWidth=3;
      ctx.beginPath();ctx.moveTo(-18,-10);ctx.lineTo(8,-14);ctx.lineTo(20,-3);
      ctx.lineTo(16,9);ctx.lineTo(-14,11);ctx.closePath();ctx.fill();ctx.stroke();
      ctx.fillStyle=flash?"#fff":col;
      ctx.beginPath();ctx.arc(11,-3,5,0,Math.PI*2);ctx.fill();
    }else if(e.type==="brute"){
      // Heavy humanoid machine.
      ctx.strokeStyle=col;ctx.lineWidth=7;
      ctx.beginPath();ctx.moveTo(-13,9);ctx.lineTo(-23,25);ctx.moveTo(13,9);ctx.lineTo(23,25);
      ctx.moveTo(-17,-3);ctx.lineTo(-29,8);ctx.moveTo(17,-3);ctx.lineTo(29,8);ctx.stroke();
      ctx.fillStyle="#17202c";ctx.strokeStyle=col;ctx.lineWidth=4;
      roundedRectPath(ctx,-22,-22,44,42,10);ctx.fill();ctx.stroke();
      ctx.fillStyle=flash?"#fff":col;
      ctx.fillRect(-13,-10,26,8);
      ctx.fillStyle="#0b111a";ctx.fillRect(-9,-9,18,5);
      ctx.fillStyle=col;ctx.fillRect(-7,5,14,7);
    }else if(e.type==="sniper"){
      // Tall floating marksman.
      ctx.strokeStyle=col;ctx.lineWidth=5;
      ctx.beginPath();ctx.moveTo(-11,11);ctx.lineTo(-19,28);ctx.moveTo(11,11);ctx.lineTo(19,28);ctx.stroke();
      ctx.fillStyle="#151528";ctx.strokeStyle=col;ctx.lineWidth=3;
      ctx.beginPath();ctx.moveTo(0,-28);ctx.lineTo(18,-8);ctx.lineTo(13,17);
      ctx.lineTo(-13,17);ctx.lineTo(-18,-8);ctx.closePath();ctx.fill();ctx.stroke();
      ctx.fillStyle=flash?"#fff":col;
      ctx.beginPath();ctx.arc(0,-6,8,0,Math.PI*2);ctx.fill();
      ctx.strokeStyle="#fff";ctx.lineWidth=2;
      ctx.beginPath();ctx.moveTo(20,-7);ctx.lineTo(43,-19);ctx.stroke();
    }else if(e.type==="tank"){
      // Massive armored crawler.
      ctx.strokeStyle=col;ctx.lineWidth=7;
      ctx.beginPath();ctx.moveTo(-25,16);ctx.lineTo(-38,30);ctx.moveTo(25,16);ctx.lineTo(38,30);ctx.stroke();
      ctx.fillStyle="#1a222b";ctx.strokeStyle=col;ctx.lineWidth=5;
      roundedRectPath(ctx,-34,-30,68,57,13);ctx.fill();ctx.stroke();
      ctx.fillStyle="#263543";
      roundedRectPath(ctx,-24,-19,48,25,7);ctx.fill();
      ctx.fillStyle=flash?"#fff":col;
      ctx.fillRect(-16,-12,32,8);
      ctx.fillStyle="#0b1118";ctx.fillRect(-10,-10,20,4);
      ctx.strokeStyle=col;ctx.lineWidth=5;
      ctx.beginPath();ctx.moveTo(29,-4);ctx.lineTo(50,-4);ctx.stroke();
    }else{
      // Boss: imposing armored command machine.
      ctx.rotate(Math.sin(t*.7)*.025);
      ctx.strokeStyle=col;ctx.lineWidth=7;
      for(const a of [-1.0,-.5,.5,1.0]){
        ctx.beginPath();ctx.moveTo(a*27,16);ctx.lineTo(a*42,32);ctx.stroke();
      }
      ctx.fillStyle="#20172a";ctx.strokeStyle=col;ctx.lineWidth=6;
      ctx.beginPath();
      ctx.moveTo(0,-67);ctx.lineTo(40,-43);ctx.lineTo(56,-5);ctx.lineTo(42,39);
      ctx.lineTo(0,61);ctx.lineTo(-42,39);ctx.lineTo(-56,-5);ctx.lineTo(-40,-43);
      ctx.closePath();ctx.fill();ctx.stroke();

      ctx.fillStyle="#35213f";
      ctx.beginPath();ctx.arc(0,0,35,0,Math.PI*2);ctx.fill();
      ctx.strokeStyle=col;ctx.lineWidth=3;
      ctx.beginPath();ctx.arc(0,0,35,0,Math.PI*2);ctx.stroke();

      ctx.fillStyle=flash?"#fff":col;
      ctx.beginPath();ctx.arc(0,0,16,0,Math.PI*2);ctx.fill();
      ctx.fillStyle="#fff";
      ctx.beginPath();ctx.arc(-5,-5,5,0,Math.PI*2);ctx.fill();

      ctx.strokeStyle=col;ctx.lineWidth=4;
      ctx.beginPath();ctx.moveTo(-50,-12);ctx.lineTo(-72,-28);
      ctx.moveTo(50,-12);ctx.lineTo(72,-28);ctx.stroke();
    }

    // Elite crown/ring.
    if(e.elite){
      ctx.strokeStyle="#fff17a";ctx.lineWidth=3;
      ctx.setLineDash([5,5]);
      ctx.beginPath();ctx.arc(0,0,e.radius+8,-Math.PI*.9,Math.PI*.9);ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.restore();

    // Health bar with a frame.
    const hp=Math.max(0,e.health/e.max_health);
    const bw=e.type==="boss"?e.radius*2.6:e.radius*2.2;
    ctx.fillStyle="rgba(4,8,13,.92)";
    roundedRectPath(ctx,e.x-bw/2,e.y-e.radius-18,bw,7,3);ctx.fill();
    ctx.fillStyle=e.type==="boss"?"#d84cff":(e.elite?"#fff17a":"#ff5c72");
    roundedRectPath(ctx,e.x-bw/2+1,e.y-e.radius-17,bw*hp-2,5,2);ctx.fill();

    if(e.elite||e.type==="boss"){
      ctx.fillStyle=col;
      ctx.textAlign="center";
      ctx.font=e.type==="boss"?"900 12px Arial":"900 9px Arial";
      ctx.fillText(e.type==="boss"?"COMMANDER":"ELITE",e.x,e.y+e.radius+19);
    }
  }

  // ---------------- PLAYERS ----------------
  for(const p of state.players){
    ctx.save();
    ctx.globalAlpha=p.alive?1:.28;
    const mine=p.id===myId;
    const body=mine?"#55dfff":"#5795ff";
    const dark=mine?"#0c2534":"#0d1a2b";
    const t=performance.now()/1000;
    const bob=p.alive?Math.sin(t*7+p.x*.01)*1.2:0;
    ctx.translate(p.x,p.y+bob);

    // Ground shadow.
    ctx.fillStyle="rgba(0,0,0,.42)";
    ctx.beginPath();ctx.ellipse(0,20,22,8,0,0,Math.PI*2);ctx.fill();

    // Aim direction.
    const a=mine?aimAngle():Math.atan2(0,1);

    // Legs.
    ctx.strokeStyle=body;ctx.lineWidth=6;ctx.lineCap="round";
    ctx.beginPath();ctx.moveTo(-8,12);ctx.lineTo(-12,26);ctx.moveTo(8,12);ctx.lineTo(12,26);ctx.stroke();

    // Backpack.
    ctx.fillStyle="#132638";ctx.strokeStyle=body;ctx.lineWidth=2;
    roundedRectPath(ctx,-20,-8,40,25,7);ctx.fill();ctx.stroke();

    // Armored torso.
    ctx.fillStyle=dark;ctx.strokeStyle=body;ctx.lineWidth=3;
    roundedRectPath(ctx,-18,-20,36,40,9);ctx.fill();ctx.stroke();

    // Chest plate.
    ctx.fillStyle=mine?"rgba(85,223,255,.16)":"rgba(87,149,255,.14)";
    roundedRectPath(ctx,-12,-12,24,19,5);ctx.fill();
    ctx.strokeStyle="rgba(255,255,255,.22)";ctx.lineWidth=1;
    ctx.stroke();

    // Shoulder pads.
    ctx.fillStyle=body;
    ctx.beginPath();ctx.arc(-19,-7,7,0,Math.PI*2);ctx.fill();
    ctx.beginPath();ctx.arc(19,-7,7,0,Math.PI*2);ctx.fill();

    // Arms.
    ctx.strokeStyle=body;ctx.lineWidth=6;
    ctx.beginPath();
    ctx.moveTo(-17,-2);ctx.lineTo(-25,10);
    ctx.moveTo(17,-2);ctx.lineTo(25,10);
    ctx.stroke();

    // Head / helmet.
    ctx.fillStyle="#101a27";ctx.strokeStyle=body;ctx.lineWidth=3;
    ctx.beginPath();ctx.arc(0,-28,13,0,Math.PI*2);ctx.fill();ctx.stroke();

    // Visor.
    ctx.fillStyle=mine?"#d9fbff":"#b8d9ff";
    ctx.globalAlpha=p.alive?.9:.5;
    roundedRectPath(ctx,-9,-31,18,7,3);ctx.fill();
    ctx.globalAlpha=p.alive?1:.28;

    // Weapon with silhouette.
    ctx.save();
    ctx.rotate(a);
    const weaponColor=state.weapons[p.weapon]?.color||"#dffaff";
    ctx.strokeStyle=weaponColor;ctx.lineWidth=5;ctx.lineCap="round";
    if(p.weapon==="shotgun"){
      ctx.beginPath();ctx.moveTo(10,0);ctx.lineTo(37,0);ctx.stroke();
      ctx.lineWidth=7;ctx.beginPath();ctx.moveTo(16,5);ctx.lineTo(34,5);ctx.stroke();
    }else if(p.weapon==="railgun"){
      ctx.lineWidth=6;ctx.beginPath();ctx.moveTo(8,0);ctx.lineTo(44,0);ctx.stroke();
      ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(17,-6);ctx.lineTo(42,-6);ctx.stroke();
    }else{
      ctx.beginPath();ctx.moveTo(9,0);ctx.lineTo(35,0);ctx.stroke();
      ctx.lineWidth=3;ctx.beginPath();ctx.moveTo(15,5);ctx.lineTo(25,5);ctx.stroke();
    }
    ctx.fillStyle=weaponColor;ctx.beginPath();ctx.arc(38,0,3,0,Math.PI*2);ctx.fill();
    ctx.restore();

    // Selection ring.
    ctx.strokeStyle=mine?"rgba(85,223,255,.75)":"rgba(87,149,255,.34)";
    ctx.lineWidth=2;
    ctx.beginPath();ctx.arc(0,2,29,0,Math.PI*2);ctx.stroke();

    // Health ring.
    if(p.alive){
      ctx.strokeStyle="rgba(255,255,255,.72)";
      ctx.lineWidth=3;
      ctx.beginPath();
      ctx.arc(0,2,33,-Math.PI/2,-Math.PI/2+Math.PI*2*Math.max(0,p.health/p.max_health));
      ctx.stroke();
    }

    // Nameplate.
    ctx.fillStyle="#fff";ctx.textAlign="center";ctx.font="900 11px Arial";
    ctx.fillText(p.name,0,-49);

    if(mine&&p.alive){
      ctx.strokeStyle="#e8fbff";ctx.lineWidth=2;ctx.globalAlpha=.75;
      ctx.beginPath();ctx.moveTo(0,0);ctx.lineTo(Math.cos(a)*48,Math.sin(a)*48);ctx.stroke();
    }

    ctx.restore();
  }

  // Damage vignette / pause treatment.
  if(state.paused){
    ctx.fillStyle="rgba(2,6,12,.22)";
    ctx.fillRect(0,0,WORLD_W,WORLD_H);
  }

  ctx.restore();
}

function drawMinimap(){
  const w=180,h=102;
  const x=innerWidth-w-16,y=innerHeight-h-150;

  ctx.save();
  ctx.fillStyle="rgba(4,10,18,.78)";
  ctx.strokeStyle="rgba(110,160,200,.25)";
  ctx.lineWidth=1;
  ctx.beginPath();
  ctx.roundRect(x,y,w,h,10);
  ctx.fill();ctx.stroke();

  const sx=w/WORLD_W,sy=h/WORLD_H;

  for(const e of state.enemies){
    ctx.fillStyle=e.type==="boss"?"#d84cff":"#ff5c72";
    ctx.fillRect(x+e.x*sx-1.5,y+e.y*sy-1.5,3,3);
  }
  for(const p of state.players){
    ctx.fillStyle=p.id===myId?"#55dfff":"#5795ff";
    ctx.beginPath();
    ctx.arc(x+p.x*sx,y+p.y*sy,3,0,Math.PI*2);ctx.fill();
  }
  ctx.restore();
}

function draw(){
  requestAnimationFrame(draw);
  ctx.clearRect(0,0,innerWidth,innerHeight);

  if(!state?.started)return;

  drawArena();
  drawMinimap();

  if(state.game_over){
    ctx.fillStyle="rgba(2,4,8,.55)";
    ctx.fillRect(0,0,innerWidth,innerHeight);
    ctx.fillStyle="#fff";
    ctx.textAlign="center";
    ctx.font="1000 46px system-ui";
    ctx.fillText(state.mode==="ffa"?"MATCH COMPLETE":"SQUAD ELIMINATED",innerWidth/2,innerHeight/2);
    ctx.font="600 13px system-ui";
    ctx.fillStyle="#9fb1c6";
    ctx.fillText("Refresh the page to play again",innerWidth/2,innerHeight/2+30);
  }
}

draw();
</script>

<div id="reviveOverlay" class="hidden">
  <div class="revive-card">
    <h2>YOU'RE DOWN</h2>
    <div class="revive-sub">Spend your coins to return to the fight.</div>
    <div class="revive-cost" id="reviveCost">$1,000</div>
    <button class="big-action" id="reviveBtn">REVIVE</button>
    <button class="big-action secondary" id="reviveWaitBtn">WAIT FOR MY TEAM</button>
    <div id="reviveStatus" class="revive-sub" style="margin-top:14px"></div>
  </div>
</div>

<div id="eliminatedOverlay" class="hidden">
  <div class="eliminated-card">
    <h2>SQUAD ELIMINATED</h2>
    <div class="revive-sub">Your entire squad has been wiped out.</div>
    <button class="big-action" id="homeAfterWipe">RETURN TO HOME</button>
  </div>
</div>

</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(HTML)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 56)
    print(" BOT ARENA // DELUXE EDITION")
    print(" http://127.0.0.1:5000")
    print(" Solo / Co-op / FFA")
    print(" Waves / Elites / Bosses / Shop / Abilities / Loot")
    print("=" * 56)

    socketio.start_background_task(game_loop)
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True,
    )
