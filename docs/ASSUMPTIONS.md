# Supuestos y límites

1. La fecha que aparece en los tres títulos identifica la ronda porque los PDF no publican otro código de ronda.
2. Cada consulta debe incluir una copia completa de las tres categorías esperadas. El usuario puede confirmar una diferencia de metadatos porque podrían existir cambios legítimos de formato.
3. El número de identificación es la llave principal. Los PDF reales no contienen nombres; el nombre solo actúa como verificación secundaria cuando una ronda futura lo publique.
4. Una fila del documento «profesionales sin plaza asignada» se clasifica como `NOT_SELECTED`, salvo que la propia fila publique de forma explícita un estado de exoneración, que se clasifica como `EXEMPT`.
5. `EXEMPT` y `NOT_SELECTED` son estados distintos y nunca se deducen uno del otro.
6. Una ausencia en los tres documentos produce `NOT_FOUND`, no `EXEMPT` ni `NOT_SELECTED`.
7. Los detalles no publicados —inicio, duración, contacto o modalidad— se omiten y nunca se deducen del código de plaza.
8. `AMBIGUOUS` conserva la evidencia disponible cuando hay contradicciones, múltiples coincidencias o confianza insuficiente; no decide arbitrariamente entre ellas.
9. La aplicación es informativa y no oficial. Los documentos fuente y la autoridad competente prevalecen.
10. Tesseract no se distribuye con el ejecutable. Los PDF de texto funcionan sin él.
