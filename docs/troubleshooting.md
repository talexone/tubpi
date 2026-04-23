# Dépannage et diagnostic

## Problème : Le moteur tourne trop longtemps

### Symptômes
- Une commande de 3 secondes prend 10-30 secondes à s'exécuter
- Le système semble ralenti ou peu réactif
- Les mouvements ne s'arrêtent pas au bon moment

### Cause probable
Surcharge du système due aux interruptions fréquentes de l'encodeur. Chaque impulsion de l'encodeur génère une interruption qui peut ralentir l'exécution du code principal.

### Solutions implémentées

#### 1. Bouncetime sur les interruptions
Les interruptions GPIO ont maintenant un `bouncetime=1ms` qui :
- Filtre les rebonds mécaniques
- Limite la fréquence maximale des interruptions à 1000 Hz
- Réduit la charge CPU sans perte significative de précision

#### 2. Lock non-bloquant
Le callback de l'encodeur utilise `acquire(blocking=False)` qui :
- Ne bloque jamais le thread principal
- Ignore les interruptions si le lock est déjà pris
- Sacrifie quelques impulsions pour garantir la réactivité

#### 3. Encodeur désactivable
Pour le diagnostic, vous pouvez désactiver temporairement l'encodeur :

```python
# Dans le code
driver = MotorDriver(enable_encoder=False)

# En ligne de commande
python test_encoder.py --no-encoder
```

### Diagnostic étape par étape

1. **Tester sans encodeur**
   ```bash
   python src/test_encoder.py --no-encoder
   ```
   Si le timing est correct → le problème vient de l'encodeur
   Si le timing est incorrect → chercher ailleurs (PWM, rampes, etc.)

2. **Vérifier la fréquence de l'encodeur**
   - Encodeur 100 impulsions/tour à 100 RPM = ~167 Hz (OK)
   - Encodeur 1000 impulsions/tour à 1000 RPM = ~16 kHz (Trop rapide!)
   
3. **Ajuster le bouncetime si nécessaire**
   Dans [motor_driver.py](../src/motor_driver.py), ligne ~75 :
   ```python
   # Augmenter le bouncetime pour réduire la fréquence
   GPIO.add_event_detect(self.encoder_a_pin, GPIO.BOTH, 
                        callback=self._encoder_callback, bouncetime=2)  # 2ms au lieu de 1ms
   ```

4. **Alternative : Utiliser le polling au lieu des interruptions**
   Si les interruptions causent trop de problèmes, on peut passer à un polling périodique (moins précis mais plus stable).

## Problème : Perte de précision de l'encodeur

### Symptômes
- Les distances mesurées sont incorrectes
- Position dérive avec le temps
- Compteur d'impulsions trop faible

### Solutions

1. **Vérifier le câblage**
   - Signaux A et B bien connectés
   - Level Shifter correctement alimenté (5V et 3.3V)
   - Masses communes entre encodeur, level shifter et Raspberry Pi

2. **Vérifier la calibration mécanique**
   ```python
   # Calculer le MM_PER_PULSE correct
   circonference_mm = 3.14159 * diametre_poulie_mm
   MM_PER_PULSE = circonference_mm / impulsions_par_tour_encodeur
   
   driver.set_mm_per_pulse(MM_PER_PULSE)
   ```

3. **Augmenter la résolution**
   Si vous perdez trop d'impulsions avec le lock non-bloquant :
   - Réduire la vitesse du moteur
   - Augmenter le temps de rampe (RAMP_STEPS)
   - Passer à un encodeur avec moins d'impulsions par tour

## Problème : Erreurs GPIO

### Symptômes
```
RuntimeError: Failed to add edge detection
```

### Solutions
1. Vérifier les permissions : `sudo usermod -a -G gpio pi`
2. Vérifier que les GPIO ne sont pas déjà utilisés
3. Nettoyer les GPIO avant de relancer : `GPIO.cleanup()`

## Monitorer les performances

Pour surveiller la charge CPU causée par les interruptions :
```bash
# Voir les interruptions par seconde
watch -n 1 'cat /proc/interrupts | grep gpio'

# Voir la charge CPU
top
# Appuyez sur '1' pour voir tous les cores
```

## Ressources

- [Documentation RPi.GPIO](https://sourceforge.net/p/raspberry-gpio-python/wiki/Inputs/)
- [Encodeurs en quadrature](https://en.wikipedia.org/wiki/Incremental_encoder)
- [Guide des interruptions GPIO](https://raspberrypi.stackexchange.com/questions/8544/gpio-interrupt-debounce)
