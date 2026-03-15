import database
from bot_core.memory_layers import update_memory_layers
from bot_core.runtime import logger
from bot_core.summarizer import run_summarizer_if_needed


async def initialize_world_dynamics():
    await database.set_world_state("world_turn_counter", "0")
    await database.set_world_state("faction_states", "{}")
    await database.set_world_state("npc_states", "{}")
    await database.set_world_state("world_clocks", "{}")
    await database.set_world_state("last_world_event", "Сцена активна. Мир реагирует только через действия героев.")


async def advance_world_turn(*, char_id: str, player_message: str, gm_response: str, chat_id: int | None = None):
    world_state = await database.get_all_world_states()
    last_world_event = f"Ход {char_id}: сцена сдвинулась после решения игрока."
    should_broadcast = False
    public_event_text = ""

    try:
        turn_counter = int(world_state.get("world_turn_counter", "0")) + 1
    except ValueError:
        turn_counter = 1

    await database.set_world_state("last_world_event", last_world_event)
    await database.set_world_state("world_turn_counter", str(turn_counter))
    await database.add_game_event("world_turn", last_world_event)

    await update_memory_layers(
        char_id=char_id,
        player_message=player_message,
        gm_response=gm_response,
        world_state={**world_state, "world_turn_counter": str(turn_counter)},
        turn_counter=turn_counter,
    )
    await run_summarizer_if_needed(
        trigger="turn",
        world_state={**world_state, "world_turn_counter": str(turn_counter)},
        force=False,
    )

    return {
        "last_world_event": last_world_event,
        "public_event_text": public_event_text,
        "should_broadcast": should_broadcast,
        "turn_counter": turn_counter,
    }
