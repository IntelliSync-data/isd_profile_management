# from enum import Enum
# from typing import Any, Dict, List


# class BaseEnum(Enum):
#     def __eq__(self, value):
#         if isinstance(self.value, value.__class__):
#             return self.value == value

#         return super().__eq__(value)

#     @classmethod
#     def to_choices(cls) -> tuple:
#         result: List[Any] = []
#         for mem in dict(cls.__members__).values():
#             result.append((mem.value, mem.name))

#         return tuple(result)

#     @classmethod
#     def switcher(cls):
#         result: Dict[Any, Any] = {}
#         for mem in dict(cls.__members__).values():
#             result.update({mem.value: mem.name})

#         return result
