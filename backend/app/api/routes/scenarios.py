from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.enums import DemoScenario
from app.schemas.ingestion import ScenarioLoadResponse
from app.services.ingestion import load_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.post(
    "/{name}/load",
    response_model=ScenarioLoadResponse,
    summary="Load a built-in demo scenario",
)
def load_demo_scenario(
    name: DemoScenario,
    session: Session = Depends(get_db),
) -> ScenarioLoadResponse:
    return load_scenario(session, name)
