from typing import TypedDict


OFFICIAL_SOURCE = "https://governo.gov.ao/angola/provincias"


class ProvinceRecord(TypedDict):
    id: str
    name: str
    capital: str


class CountryRecord(TypedDict):
    id: str
    name: str
    code: str
    capital: str
    province_count: int


ANGOLA: CountryRecord = {
    "id": "angola",
    "name": "Angola",
    "code": "AGO",
    "capital": "Luanda",
    "province_count": 21,
}


PROVINCES: list[ProvinceRecord] = [
    {"id": "bengo", "name": "Bengo", "capital": "Dande"},
    {"id": "benguela", "name": "Benguela", "capital": "Benguela"},
    {"id": "bie", "name": "Bié", "capital": "Cuito"},
    {"id": "cabinda", "name": "Cabinda", "capital": "Cabinda"},
    {"id": "cuando", "name": "Cuando", "capital": "Mavinga"},
    {"id": "cuanza-norte", "name": "Cuanza Norte", "capital": "Cazengo"},
    {"id": "cuanza-sul", "name": "Cuanza Sul", "capital": "Sumbe"},
    {"id": "cubango", "name": "Cubango", "capital": "Menongue"},
    {"id": "cunene", "name": "Cunene", "capital": "Cuanhama"},
    {"id": "huambo", "name": "Huambo", "capital": "Huambo"},
    {"id": "huila", "name": "Huíla", "capital": "Lubango"},
    {"id": "icolo-e-bengo", "name": "Icolo e Bengo", "capital": "Catete"},
    {"id": "luanda", "name": "Luanda", "capital": "Ingombota"},
    {"id": "lunda-norte", "name": "Lunda Norte", "capital": "Dundo"},
    {"id": "lunda-sul", "name": "Lunda Sul", "capital": "Saurimo"},
    {"id": "malanje", "name": "Malanje", "capital": "Malanje"},
    {"id": "moxico", "name": "Moxico", "capital": "Luena"},
    {"id": "moxico-leste", "name": "Moxico Leste", "capital": "Cazombo"},
    {"id": "namibe", "name": "Namibe", "capital": "Moçâmedes"},
    {"id": "uige", "name": "Uíge", "capital": "Uíge"},
    {"id": "zaire", "name": "Zaire", "capital": "Mbanza Kongo"},
]
