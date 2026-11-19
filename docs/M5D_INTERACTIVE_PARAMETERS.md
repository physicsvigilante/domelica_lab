# M5D — HTML-to-native runtime connection

The M5C Linux x86-64 bundle can start a **loopback-only parameter application**.
Open its page in a browser, enter cart/bob masses and spring stiffness, set an
angle in degrees, and click **Run fresh simulation**. The application validates
the values, invokes the *same unchanged* precompiled OpenModelica solver, exports
a fresh trajectory and observations, then opens the native Three.js playback
in the page. A link saves the newly produced HTML recording for offline sharing.

The browser does not contain a solver or execute native code directly. The
small Python server and the packaged compiled model run on the same computer.
Neither the OpenModelica compiler, the Modelica Standard Library, GCC, make,
Node, nor third-party Python modules are needed by the recipient.

## Start

Download the **compiled-model-linux-x86_64** artifact from the workflow
attached to the reviewed M5D commit. Extract the internal
**compiled-model-linux-x86_64.tar.gz**, then run from the parent folder:

    python3 compiled-model/scripts/serve_compiled_lab.py \
      --bundle compiled-model --results-dir parameter-runs --port 8765

Open **http://127.0.0.1:8765/** while the server remains running.

Each successful click generates a distinct recording folder beneath
parameter-runs. The service retains the most recent eight recordings,
removing older ones when additional successful runs complete. Use the
**Save standalone recording** link to keep an HTML that plays without
the server. The server's terminal displays diagnostics if a native run fails.

The supported parameters are declared in the M5C manifest: cart mass,
bob mass, spring stiffness and release angle. The first three must be
finite and strictly positive; the angle must be strictly between −90°
and +90°. The UI displays degrees but the runtime accepts radians.
An otherwise valid combination can still fail the unchanged model's
physical assertions or numerical integration.

The interface changes **run-start values**, not the physical arrangement
or values mid-flight. Another body or joint requires a new compilation.
No compiler is invoked for a supported numerical rerun.

## HTTP endpoints (local machine only)

- GET / serves the parameter form and same-origin /app.js.
- GET /api/config reports the permitted names, units and defaults.
- POST /api/run takes a JSON object with a single "parameters" property,
  for example:

      {"parameters":{"cartMass":3.37,"bobMass":0.76,"springStiffness":18,"initialAngle":0.55}}

- A successful response includes the actual native parameter values,
  sample count, HTML SHA-256, zero runtime compiler calls, and a
  /runs/<random-id>/viewer.html URL. The page uses that URL in an iframe,
  without rebuilding the physical model.

The bridge accepts only allowlisted finite numerical values, rejects
unknown properties, limits request size, and permits one simulation at a
time. It is bound to 127.0.0.1, checks Host and Origin, requires a custom
same-origin JSON request header, invokes subprocesses with argument arrays
rather than a shell, and enforces per-process timeouts. Arbitrary command
lines, source code, paths or model names cannot be submitted through the API.

This is a **local single-user prototype**. Do not expose or reverse-proxy it
to the public internet. A remote multiuser service would additionally
require authentication, per-request isolation, quotas, rate limits, workload
limits, and a different deployment architecture.

## Qualification

The updated **Compiled Parameter Lab** workflow tests:

1. Existing M5C compile-once and three preset runs in a container without
   OpenModelica or a C/C++ toolchain.
2. Five HTTP security/input guard tests without invoking the solver.
3. One fresh **non-preset** HTTP request in that same clean runtime;
   verifies its actual parameters, exact resulting HTML hash and
   immutable compiled executable.
4. Existing native result-reader comparison and generated 3D viewer checks.
5. Chromium interaction with the actual parameter form and request format,
   using a mocked HTTP response solely for the UI check. The real HTTP
   native run is checked separately in the clean container.

The unchanged M5 observation renderer and Modelica equations remain the
source of physics and presentation. No independent trajectory/energy
accuracy campaign or broad parameter sweep is introduced.

### Other distribution choices

- **Hosted simulation server:** same compiled executable on a remote
  server; browser users install nothing. Requires production security.
- **Desktop shell (Tauri/Electron):** friendly one-click installer that
  starts the local runtime and embeds the same UI; platform-specific
  packaging required.
- **Precomputed HTML:** easiest offline distribution, but users can
  switch only among saved recordings.
- **FMU or WebAssembly runtime:** potentially useful for other platforms
  or browser-only solving, but additional runtime/export qualification
  is needed; it does not create arbitrary new Modelica topologies.
