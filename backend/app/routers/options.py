from fastapi import APIRouter, Depends

from ..db import get_conn
from ..deps import Admin, current_admin

router = APIRouter(prefix="/api/options", tags=["options"])


@router.get("")
def options(admin: Admin = Depends(current_admin), conn=Depends(get_conn)):
    brands = admin.allowed_brands
    return {
        "brands": conn.execute(
            "SELECT id, name, currency FROM brands WHERE id = ANY(%s) ORDER BY id", (brands,)
        ).fetchall(),
        "vip_levels": conn.execute(
            "SELECT id, brand_id, level, name FROM vip_levels WHERE brand_id = ANY(%s) ORDER BY brand_id, level",
            (brands,),
        ).fetchall(),
        "tags": conn.execute(
            "SELECT id, brand_id, name FROM tags WHERE brand_id = ANY(%s) ORDER BY brand_id, name", (brands,)
        ).fetchall(),
        "statuses": ["normal", "blacklist", "leaving", "left"],
    }
