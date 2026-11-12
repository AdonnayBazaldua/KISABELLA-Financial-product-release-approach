import { describe, expect, it } from "vitest";
import { warnFlagLabel } from "./verdicts";

describe("warnFlagLabel", () => {
  it("traduce los flags conocidos del backend", () => {
    expect(warnFlagLabel("warn_fx")).toBe("TC distinto al de Banxico");
    expect(warnFlagLabel("warn_no_web")).toBe("Sin búsqueda web");
  });

  it("muestra tal cual un flag desconocido en vez de ocultarlo", () => {
    expect(warnFlagLabel("warn_nuevo")).toBe("warn_nuevo");
  });
});
