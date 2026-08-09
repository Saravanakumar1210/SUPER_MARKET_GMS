from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.password_policy import validate_password_strength


class CategoryOut(BaseModel):
    ProductCategoryID: str
    CategoryName: str
    Product_Count: int
    Min_Price: float
    Max_Price: float
    Avg_Price: float
    Median_Price: float
    description: str | None = None


class SubcategoryOut(BaseModel):
    ProductCategoryID: str
    CategoryName: str
    ProductSubCategoryID: str
    SubCategoryName: str
    Product_Count: int
    Min_Price: float
    Max_Price: float
    Avg_Price: float
    Median_Price: float


class ProductOut(BaseModel):
    productId: str
    categoryId: str
    categoryName: str
    subCategoryId: str
    subCategoryName: str
    productName: str
    displayName: str
    weightKG: float | None = None
    packType: str = ""
    unitLabel: str = ""
    locationId: int = 52
    salesUnitTypeId: int = 1
    flaggedCategoryMismatch: bool = False
    productDescription: str = ""
    primaryImageUrl: str | None = None
    isFeatured: bool = False
    isBestSeller: bool = False
    isNewArrival: bool = False
    isHotOffer: bool = False
    isExclusive: bool = False
    discountPercent: int = 0
    kitchenCulture: str | None = None


class KitchenCultureOut(BaseModel):
    key: str
    label: str


class ProductListResponse(BaseModel):
    items: list[ProductOut]
    total_count: int
    total_pages: int
    current_page: int
    per_page: int


class ProductImageOut(BaseModel):
    id: int
    product_id: str
    image_url: str
    alt_text: str | None = None
    is_primary: bool
    display_order: int


class BannerOut(BaseModel):
    id: int
    title: str
    subtitle: str | None = None
    image_url: str
    link_url: str | None = None
    display_order: int


class CultureOut(BaseModel):
    id: int
    title: str
    image_url: str
    link_url: str | None = None
    display_order: int


class TestimonialOut(BaseModel):
    initials: str
    name: str
    text: str
    rating: int = 5


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone_country: str = Field(default="GB", min_length=2, max_length=5)
    phone: str = Field(min_length=7, max_length=30)
    address: str = Field(min_length=3, max_length=500)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        return validate_password_strength(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("phone_country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return (value or "GB").strip().upper()


class LoginIn(BaseModel):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class CustomerProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone_country: str | None = Field(default=None, min_length=2, max_length=5)
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    address: str | None = Field(default=None, min_length=3, max_length=500)

    @field_validator("phone_country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()


class UserProfileOut(BaseModel):
    id: str
    name: str | None = None
    username: str | None = None
    email: str
    phone: str | None = None
    phone_country: str | None = None
    address: str | None = None
    role: str


class AuthOut(BaseModel):
    session_token: str
    user: UserProfileOut


class CartItemIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(ge=1, le=999)

    @field_validator("product_name")
    @classmethod
    def normalize_product_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("product_name is required")
        return cleaned


class CartReplaceIn(BaseModel):
    items: list[CartItemIn] = Field(default_factory=list, max_length=500)


class CartItemOut(BaseModel):
    product_name: str
    quantity: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    updated_at: float | None = None  # unix seconds; max row updated_at for LWW sync


class CatalogMetadataOut(BaseModel):
    categoryStats: list[dict]
    subcategoryStats: list[dict]
    promotionBannerImages: list[str]
    promotionBanners: list[dict] = []
    siteSettings: dict[str, str] = {}


class CatalogProductsBulkOut(BaseModel):
    products: list[dict]


class BootstrapOut(BaseModel):
    categoryStats: list[dict]
    subcategoryStats: list[dict]
    products: list[dict]
    productImageById: dict[str, str]
    productHomeImageById: dict[str, str]
    promotionBannerImages: list[str]
    promotionBanners: list[dict] = []
    siteSettings: dict[str, str] = {}


class AdminStatsOut(BaseModel):
    total_products: int
    total_categories: int
    total_subcategories: int
    flagged_products: int
    avg_price: float


class CouponOut(BaseModel):
    code: str
    type: str
    value: float
    min: float
    active: bool = True


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdminCategoryIn(StrictBaseModel):
    category_id: str | None = Field(default=None, max_length=10)
    ProductCategoryID: str | None = Field(default=None, max_length=10)
    category_name: str | None = Field(default=None, min_length=1, max_length=100)
    CategoryName: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    slug: str | None = Field(default=None, max_length=120)
    icon_image_url: str | None = None
    banner_image_url: str | None = None
    is_active: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=32767)


class AdminSubcategoryIn(StrictBaseModel):
    subcategory_id: str | None = Field(default=None, max_length=15)
    ProductSubCategoryID: str | None = Field(default=None, max_length=15)
    category_id: str | None = Field(default=None, max_length=10)
    ProductCategoryID: str | None = Field(default=None, max_length=10)
    subcategory_name: str | None = Field(default=None, min_length=1, max_length=100)
    SubCategoryName: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    slug: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=32767)


class AdminProductIn(StrictBaseModel):
    product_id: str | None = Field(default=None, max_length=25)
    productId: str | None = Field(default=None, max_length=25)
    category_id: str | None = Field(default=None, max_length=10)
    subcategory_id: str | None = Field(default=None, max_length=15)
    product_name: str | None = Field(default=None, min_length=1, max_length=255)
    brand: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=5000)
    selling_price: float | None = Field(default=None, ge=0)
    compare_price: float | None = Field(default=None, ge=0)
    discount_percent: int | None = Field(default=None, ge=0, le=100)
    unit_label: str | None = Field(default=None, max_length=50)
    weight_kg: float | None = Field(default=None, ge=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    min_order_qty: int | None = Field(default=None, ge=1, le=32767)
    is_wholesale: bool | None = None
    is_featured: bool | None = None
    is_best_seller: bool | None = None
    is_new_arrival: bool | None = None
    is_hot_offer: bool | None = None
    is_exclusive: bool | None = None
    is_active: bool | None = None
    kitchen_culture: str | None = Field(default=None, max_length=30)


class AdminBulkProductActionIn(StrictBaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=1000)
    action: str = Field(pattern="^(activate|deactivate|delete|category)$")
    category_id: str | None = Field(default=None, max_length=10)
    subcategory_id: str | None = Field(default=None, max_length=15)


class AdminBulkDiscountIn(StrictBaseModel):
    discount_percent: int = Field(ge=0, le=100)
    category_id: str | None = Field(default=None, max_length=10)
    subcategory_id: str | None = Field(default=None, max_length=15)


class AdminClearDiscountsIn(StrictBaseModel):
    product_ids: list[str] | None = Field(default=None, max_length=1000)


class AdminProductImageIn(StrictBaseModel):
    image_url: str | None = None
    imageUrl: str | None = None
    is_primary: bool | None = None
    isPrimary: bool | None = None
    alt_text: str | None = Field(default=None, max_length=255)
    altText: str | None = Field(default=None, max_length=255)
    display_order: int | None = Field(default=None, ge=0, le=32767)
    displayOrder: int | None = Field(default=None, ge=0, le=32767)


class AdminBannerIn(StrictBaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    subtitle: str | None = Field(default=None, max_length=255)
    image_url: str | None = None
    link_url: str | None = None
    display_order: int | None = Field(default=None, ge=0, le=32767)
    is_active: bool | None = None
    direction: str | None = Field(default=None, pattern="^(left|right)$")


class AdminCultureIn(StrictBaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    image_url: str | None = None
    link_url: str | None = None
    display_order: int | None = Field(default=None, ge=0, le=32767)
    is_active: bool | None = None
    direction: str | None = Field(default=None, pattern="^(left|right)$")


class AdminCouponIn(StrictBaseModel):
    code: str = Field(min_length=1, max_length=40)
    type: str = Field(pattern="^(percent|fixed)$")
    value: float = Field(ge=0)
    min: float = Field(default=0, ge=0)
    active: bool = True
    desc: str | None = Field(default=None, max_length=255)


class AdminTestimonialIn(StrictBaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=100)
    customer_initial: str | None = Field(default=None, max_length=5)
    is_verified_customer: bool | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    quote: str | None = Field(default=None, min_length=1, max_length=5000)
    is_featured: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=32767)


class AdminSiteSettingsIn(BaseModel):
    model_config = ConfigDict(extra="allow")
