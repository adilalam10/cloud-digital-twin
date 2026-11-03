from pydantic import BaseModel, Field, ConfigDict

class SimulationRequest(BaseModel):
    scenario: str = Field(pattern=r"^(workload|failure)$")
    workload_change: float = Field(default=40, ge=-90, le=300)
    server_id: int | None = None

class ServerCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=60)
    cpu: float = Field(default=10, ge=0, le=100)
    ram: float = Field(default=20, ge=0, le=100)
    storage: float = Field(default=20, ge=0, le=100)
    network: float = Field(default=10, ge=0, le=100)
    workload: float = Field(default=10, ge=0, le=100)
