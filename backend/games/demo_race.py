# Juego de demostración y plantilla de referencia: gana quien llega antes al número de clics objetivo.
# Para crear un juego nuevo, copia este fichero, cambia id/name/límites y la lógica, y regístralo en games/__init__.py.
from backend.game_rooms import GameHandler, register


@register
class DemoRace(GameHandler):
    id = "demo_race"
    name = "Carrera de clics (demo)"
    min_players = 2
    max_players = 4

    def default_settings(self):
        return {"target": 10}

    async def on_start(self, room):
        room.data = {"clicks": {str(p.user_id): 0 for p in room.players.values()}}

    async def on_message(self, room, player, msg):
        if msg.get("action") != "click":
            return
        clicks = room.data["clicks"]
        clicks[str(player.user_id)] += 1
        await room.broadcast("game", action="progress", clicks=clicks)
        if clicks[str(player.user_id)] >= room.settings["target"]:
            ranked = sorted(room.players.values(), key=lambda p: -clicks[str(p.user_id)])
            await room.finish([{"userId": p.user_id, "username": p.username,
                                "score": clicks[str(p.user_id)], "rank": i + 1}
                               for i, p in enumerate(ranked)])

    def snapshot(self, room, player):
        return {"clicks": room.data.get("clicks", {}), "target": room.settings["target"]}
