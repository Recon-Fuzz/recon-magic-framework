-> We need to add each new repo we create to the Recon App so we have cloning permissions.
-> TODO: Fix this -> TODO: GH Auth
TODO: GITHUB_APP_INSTALLATION_ID
----------
-> Then add auto run on the Magic Job?
-> Every job that is E2E also has the Auto-Run.
TODO: This can likely be done in a much simpler way.
Just give it a way to trigger a hardcoded job or smth, with proper validation.
Basically the worker can do smth like: POST /newEchidna/:jobId and be done with it.
So the jobs are standardized.

Then from UI you can dispatch custom jobs.
----------