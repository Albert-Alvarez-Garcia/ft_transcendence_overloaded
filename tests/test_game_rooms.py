# Pruebas de la capa de salas, sin servidor ni base de datos:  python3 -m unittest discover -s tests -t . -v
import asyncio
import unittest

from backend.game_rooms import RoomManager
from backend.games import demo_race  # noqa: F401


class FakeWS:
    def __init__(self):
        self.sent, self.closed = [], None

    async def send_json(self, data):
        self.sent.append(data)

    async def close(self, code=1000):
        self.closed = code

    def types(self):
        return [m["type"] for m in self.sent]

    def last(self, type_):
        return [m for m in self.sent if m["type"] == type_][-1]


class RoomTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.recorded = []
        self.mgr = RoomManager(record_match=lambda g, c, r: self.recorded.append((g, c, r)), grace_seconds=0.05)

    async def two_players(self):
        room, _ = self.mgr.create("demo_race", 1, settings={"target": 3})
        w1, w2 = FakeWS(), FakeWS()
        _, p1, _ = await self.mgr.join(room.code, 1, "ana", w1)
        _, p2, _ = await self.mgr.join(room.code, 2, "beto", w2)
        return room, p1, p2, w1, w2

    async def test_unknown_game_and_bad_settings(self):
        self.assertEqual(self.mgr.create("nope", 1)[1], "unknown_game")
        self.assertEqual(self.mgr.create("demo_race", 1, max_players=99)[1], "invalid_settings")

    async def test_join_notifies_others(self):
        room, p1, p2, w1, w2 = await self.two_players()
        self.assertEqual(w2.types()[0], "room_state")
        self.assertIn("player_joined", w1.types())
        self.assertEqual(len(w2.last("room_state")["players"]), 2)

    async def test_start_rules_and_full_game(self):
        room, p1, p2, w1, w2 = await self.two_players()
        await self.mgr.handle(room, p2, {"type": "start"})
        self.assertEqual(w2.last("error")["code"], "not_host")
        await self.mgr.handle(room, p1, {"type": "game", "action": "click"})
        self.assertEqual(w1.last("error")["code"], "not_playing")
        await self.mgr.handle(room, p1, {"type": "start"})
        self.assertEqual(room.phase, "playing")
        for _ in range(3):
            await self.mgr.handle(room, p2, {"type": "game", "action": "click"})
        self.assertEqual(room.phase, "finished")
        self.assertEqual(w1.last("finished")["results"][0]["username"], "beto")
        self.assertEqual(self.recorded[0][0], "demo_race")

    async def test_not_enough_players(self):
        room, _ = self.mgr.create("demo_race", 1)
        w = FakeWS()
        _, p, _ = await self.mgr.join(room.code, 1, "ana", w)
        await self.mgr.handle(room, p, {"type": "start"})
        self.assertEqual(w.last("error")["code"], "not_enough_players")

    async def test_late_join_rejected_but_reconnect_allowed(self):
        room, p1, p2, w1, w2 = await self.two_players()
        await self.mgr.handle(room, p1, {"type": "start"})
        self.assertEqual((await self.mgr.join(room.code, 3, "caro", FakeWS()))[2], "room_closed")
        await self.mgr.leave(room, p2, w2)
        self.assertEqual(w1.last("player_status")["connected"], False)
        w2b = FakeWS()
        _, _, err = await self.mgr.join(room.code, 2, "beto", w2b)
        self.assertIsNone(err)
        self.assertEqual(w2b.last("room_state")["phase"], "playing")
        self.assertIn("clicks", w2b.last("room_state")["gameState"])

    async def test_same_user_replaces_old_connection(self):
        room, p1, p2, w1, w2 = await self.two_players()
        await self.mgr.join(room.code, 1, "ana", FakeWS())
        self.assertEqual(w1.closed, 4409)

    async def test_lobby_leave_reassigns_host_and_deletes_empty_room(self):
        room, p1, p2, w1, w2 = await self.two_players()
        await self.mgr.leave(room, p1, w1)
        self.assertEqual(room.host_id, 2)
        await self.mgr.leave(room, p2, w2)
        self.assertNotIn(room.code, self.mgr.rooms)

    async def test_chat_rate_limit(self):
        room, p1, p2, w1, w2 = await self.two_players()
        for _ in range(6):
            await self.mgr.handle(room, p1, {"type": "chat", "text": "hola"})
        self.assertEqual(w1.types().count("chat"), 5)
        self.assertEqual(w1.last("error")["code"], "too_fast")

    async def test_unjoined_room_expires(self):
        room, _ = self.mgr.create("demo_race", 1)
        await asyncio.sleep(0.15)
        self.assertNotIn(room.code, self.mgr.rooms)


if __name__ == "__main__":
    unittest.main()
