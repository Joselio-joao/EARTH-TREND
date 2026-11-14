"""Interpretação por regras (sem IA): descreve só o que o motor estatístico calculou."""

MINUS = "\u2212"

DOES_NOT_PROVE = [
    "Não identifica automaticamente a causa da alteração.",
    "Não substitui a validação da qualidade dos dados e da sazonalidade.",
    "A importância ambiental não é igual à significância estatística.",
]


def fmt_num(x, nd=2, signed=False):
    """Número à portuguesa (vírgula decimal, sinal menos tipográfico)."""
    if x is None or x != x:
        return "n/d"
    body = ("%.*f" % (nd, abs(x))).replace(".", ",")
    is_zero = float(body.replace(",", ".")) == 0.0
    if x < 0 and not is_zero:
        return MINUS + body
    if signed and x > 0 and not is_zero:
        return "+" + body
    return body


def fmt_auto(x, signed=False):
    """Casas decimais conforme a grandeza: 1234, 12,3, 1,23, 0,123, 0,0123."""
    if x is None or x != x:
        return "n/d"
    a = abs(x)
    nd = 0 if a >= 100 else 1 if a >= 10 else 2 if a >= 1 else 3 if a >= 0.1 else 4
    return fmt_num(x, nd, signed)


def fmt_p(p):
    if p is None or p != p:
        return "n/d"
    return "< 0,001" if p < 0.001 else fmt_num(p, 3)


def interpret(trend, region, variable, first, last, unit, scale_label):
    var = variable[:1].lower() + variable[1:]
    direction = trend["direction"]
    level = None
    if direction == "inconclusive":
        summary = "Não foi possível concluir sobre a tendência: %s." % trend["reason"]
    else:
        sen, mk = trend["sen"], trend["mann_kendall"]
        level = sen["ci_level"]
        slope = fmt_auto(sen["slope_per_year"], True)
        ci = "intervalo de confiança de %d%%: %s a %s" % (
            round(level * 100), fmt_auto(sen["ci_low"], True), fmt_auto(sen["ci_high"], True))
        head = "Em %s, entre %s e %s, a série %s de %s" % (region, first, last, scale_label, var)
        if direction == "no_trend":
            summary = ("%s não mostra evidência estatística suficiente de tendência (p = %s; declive de Sen de %s %s "
                       "por ano; %s). Isto não prova que a variável seja estável: a variabilidade pode ser grande "
                       "ou a série curta." % (head, fmt_p(mk["p_value"]), slope, unit, ci))
        else:
            word = "aumento" if direction == "increasing" else "diminuição"
            summary = ("%s mostra evidência estatística de %s: declive de Sen de %s %s por ano (%s; p = %s). "
                       "Isto descreve o que os dados mostram e não explica a causa."
                       % (head, word, slope, unit, ci, fmt_p(mk["p_value"])))
    return {"summary": summary, "confidence_level": level, "does_not_prove": list(DOES_NOT_PROVE)}
