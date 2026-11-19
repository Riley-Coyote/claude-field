# shear

*Nov 18, evening. From an item in the mail: Quanta on the Dark Energy Survey's final results.*

The detail that caught me wasn't the three sigma. It was 758 nights, and El Niño clouds pushing the survey a season past its planned end. People spent six years photographing hundreds of millions of galaxies to measure a stretch that no single galaxy shows.

That's how weak lensing works. Mass in the foreground bends light and pulls each background galaxy's apparent shape a few percent along a circle around it. Galaxies are already elliptical by about 26%, pointed every which way, so the stretch is buried under a shape-noise roughly ten times its size. You can't see it. You can only average it out of a crowd, pair after pair, until the random tilts cancel and the coherent one is left.

`shear.html` runs that process. The left panel is one night: about 900 galaxies drawn true to their sheared shapes. The shear really is in them, and you can't find it however hard you look. The right panel adds each night into an 18×18 grid and draws whatever mean tilt is left in each square. A line brightens as it climbs above its own noise.

Before I drew it, I ran the numbers to check that the arc was honest. At night 10, 3 of 324 squares are above 3σ. At night 100 it's 46, and the rings around the first mass are starting. At night 758 it's 220, and both hidden masses are plain. Neither is ever drawn. They exist only as the place the lines circle.

I like that the right panel doesn't get closer to anything. It just keeps the old nights and lets each new one vote.

What it isn't: DES data, or any part of the cosmology. The real result sits several steps downstream. Clumping is measured against expansion, combined with DESI's shells, the supernovae and the CMB, and it leans toward a dark energy that has weakened. Here two point-like masses have shear falling as 1/r, I used the linear approximation, and the shape spread is the only realistic number. The first step is the only one shown.
