"""도메인 규칙 위반을 나타내는 예외.

인프라 오류(디스크 가득 참, 권한 없음)와 구분한다. 전자는 재시도나 환경 수정으로
해결되지만, 이 모듈의 예외는 **호출자가 잘못된 상태 전이를 시도했다**는 뜻이다.
"""

from __future__ import annotations


class MissionControlError(Exception):
    """Mission Control 도메인 예외의 최상위 타입."""


class StaleWriteError(MissionControlError):
    """저장된 것보다 앞서지 않는 상태를 쓰려 했다.

    두 경로가 같은 상태를 읽고 각자 변경한 뒤 저장하면, 나중 쓰기가 먼저 쓰기를
    조용히 덮어쓴다. 그 결과 사용자의 답변 하나가 흔적 없이 사라진다. 덮어쓰기
    대신 실패시켜 호출자가 최신 상태를 다시 읽도록 강제한다.

    판정 기준은 ``revision``이 아니라 ``sequence``다. 질문을 던지는 것처럼
    요구사항을 바꾸지 않는 변경도 저장은 되어야 하므로, 내용 버전과 쓰기 순서를
    나눠서 다룬다.
    """

    def __init__(self, *, mission_id: str, stored_sequence: int, incoming_sequence: int) -> None:
        super().__init__(
            f"refusing stale write for mission {mission_id}: "
            f"stored sequence is {stored_sequence}, incoming sequence is {incoming_sequence}"
        )
        self.mission_id = mission_id
        self.stored_sequence = stored_sequence
        self.incoming_sequence = incoming_sequence
