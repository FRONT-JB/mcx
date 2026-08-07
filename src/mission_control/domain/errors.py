"""도메인 규칙 위반을 나타내는 예외.

인프라 오류(디스크 가득 참, 권한 없음)와 구분한다. 전자는 재시도나 환경 수정으로
해결되지만, 이 모듈의 예외는 **호출자가 잘못된 상태 전이를 시도했다**는 뜻이다.
"""

from __future__ import annotations


class MissionControlError(Exception):
    """Mission Control 도메인 예외의 최상위 타입."""


class StaleRevisionError(MissionControlError):
    """이미 지나간 revision을 기준으로 상태를 갱신하려 했다.

    두 경로가 같은 상태를 읽고 각자 변경한 뒤 저장하면, 나중 쓰기가 먼저 쓰기를
    조용히 덮어쓴다. 그 결과 사용자의 답변 하나가 흔적 없이 사라진다. 덮어쓰기
    대신 실패시켜 호출자가 최신 상태를 다시 읽도록 강제한다.
    """

    def __init__(self, *, mission_id: str, stored_revision: int, incoming_revision: int) -> None:
        super().__init__(
            f"refusing stale write for mission {mission_id}: "
            f"stored revision is {stored_revision}, incoming revision is {incoming_revision}"
        )
        self.mission_id = mission_id
        self.stored_revision = stored_revision
        self.incoming_revision = incoming_revision
