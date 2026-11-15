/** 사진은 서버에 보내지 않고 작은 JPEG로 변환해 탭 안에서만 사용한다. */
export async function prepareProfilePhoto(file: File): Promise<string> {
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("JPG, PNG, WebP 사진을 선택해 주세요.");
  if (file.size > 10 * 1024 * 1024) throw new Error("사진이 너무 커요. 10MB 이하로 선택해 주세요.");
  let image: ImageBitmap;
  try { image = await createImageBitmap(file); }
  catch { throw new Error("사진을 읽지 못했어요. 다른 사진을 선택해 주세요."); }
  try {
    if (!image.width || !image.height || image.width * image.height > 48_000_000) throw new Error("사진 크기가 너무 커요. 해상도를 줄인 사진을 선택해 주세요.");
    const canvas = document.createElement("canvas");
    canvas.width = 256; canvas.height = 256;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("사진을 준비하지 못했어요. 다시 시도해 주세요.");
    const size = Math.min(image.width, image.height);
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, 256, 256);
    context.drawImage(image, (image.width - size) / 2, (image.height - size) / 2, size, size, 0, 0, 256, 256);
    return canvas.toDataURL("image/jpeg", 0.85);
  } finally { image.close(); }
}
