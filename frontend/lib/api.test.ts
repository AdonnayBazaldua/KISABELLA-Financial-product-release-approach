import { describe, expect, it } from "vitest";
import { errorDetail } from "./api";

describe("errorDetail", () => {
  it("convierte los errores de validación de FastAPI (422) en texto legible", () => {
    const body = {
      detail: [
        { loc: ["body", "target_price"], msg: "Input should be greater than 0" },
        { loc: ["body", "product_name"], msg: "Field required" },
      ],
    };
    expect(errorDetail(body, 422)).toBe(
      "target_price: Input should be greater than 0; product_name: Field required"
    );
  });

  it("usa el mensaje del backend cuando es texto", () => {
    expect(errorDetail({ detail: "Evaluación no encontrada" }, 404)).toBe("Evaluación no encontrada");
    expect(errorDetail({ detail: { code: "X", detail: "Límite alcanzado" } }, 429)).toBe("Límite alcanzado");
  });

  it("cae al código HTTP si no hay detalle", () => {
    expect(errorDetail(null, 500)).toBe("HTTP 500");
  });
});
