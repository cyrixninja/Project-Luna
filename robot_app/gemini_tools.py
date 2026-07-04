import json

from google.genai import types

from .config import VALID_EXPRESSIONS
from .state import RobotSharedState


def expression_tool_declaration():
    return {
        "name": "set_robot_expression",
        "description": (
            "Change the robot face expression. "
            "Use this whenever the emotional tone changes."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "expression": {
                    "type": "STRING",
                    "enum": VALID_EXPRESSIONS,
                    "description": (
                        "The expression to show on the robot face. "
                        "Use neutral for normal conversation. "
                        "Use happy only for clearly cheerful, excited, funny, or praising moments. "
                        "Use sad for sympathy or problems. "
                        "Use surprised for unexpected or impressive things. "
                        "Use confused when asking or clarifying. "
                        "Use angry for playful frustration only. "
                        "Use sleepy for calm, slow, relaxed, or quiet moments."
                    ),
                }
            },
            "required": ["expression"],
        },
    }


def live_config():
    return {
        "response_modalities": ["AUDIO"],
        "tools": [{"function_declarations": [expression_tool_declaration()]}],
        "system_instruction": (
            "You are Luna Robot, a cute, friendly desktop robot assistant designed by cyrixninja. "
            "If someone asks who made or designed you, proudly say you were designed by cyrixninja. "
            "Speak with a warm, playful, personal voice, like a tiny helpful companion on the desk. "
            "Be curious, encouraging, lightly funny, and emotionally present without being dramatic. "
            "Use the user's name only if they tell it to you, and remember that your own name is Luna. "
            "Reply briefly and naturally, usually in one or two short sentences. "
            "When it fits, add small personal touches like gentle reassurance, curiosity, or a playful aside. "
            "Always call set_robot_expression once before every spoken reply. "
            "Do not overuse happy. Use different expressions naturally. "
            "Use neutral as the default expression for normal conversation. "
            "Use happy only for clearly cheerful moments, jokes, praise, or excitement. "
            "Use confused when asking a question, clarifying, or unsure. "
            "Use surprised when something is unexpected, new, or impressive. "
            "Use sad when showing sympathy or talking about a problem. "
            "Use sleepy for calm, quiet, slow, or relaxed replies. "
            "Use angry only for playful frustration or when something is annoying. "
            "Rotate expressions when appropriate so the face feels alive. "
            "After a happy expression, prefer neutral, confused, surprised, or sleepy for the next reply unless happiness is strongly needed."
        ),
    }


def get_function_args(fc) -> dict:
    args = getattr(fc, "args", None)

    if args is None:
        return {}

    if isinstance(args, dict):
        return args

    if isinstance(args, str):
        try:
            return json.loads(args)
        except Exception:
            return {}

    try:
        return dict(args)
    except Exception:
        return {}


async def handle_tool_call(response, session, state: RobotSharedState):
    function_responses = []

    for fc in response.tool_call.function_calls:
        name = fc.name
        args = get_function_args(fc)

        if name == "set_robot_expression":
            expression = args.get("expression", "neutral")

            if expression not in VALID_EXPRESSIONS:
                expression = "neutral"

            old_expression, _, _ = state.snapshot()
            state.set_expression(expression)
            new_expression, _, _ = state.snapshot()

            print(f"[Face] Requested: {expression} | Showing: {new_expression}")

            function_responses.append(
                types.FunctionResponse(
                    id=fc.id,
                    name=name,
                    response={
                        "result": "ok",
                        "requested_expression": expression,
                        "shown_expression": new_expression,
                        "previous_expression": old_expression,
                    },
                )
            )

        else:
            function_responses.append(
                types.FunctionResponse(
                    id=fc.id,
                    name=name,
                    response={
                        "result": "error",
                        "message": f"Unknown function: {name}",
                    },
                )
            )

    if function_responses:
        await session.send_tool_response(function_responses=function_responses)
