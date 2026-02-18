# Express GH to ABI
## Documentation

https://gist.github.com/GalloDaSballo/d1bee970f5605b05e062f6aea39b13e6

## TODOs

See TODO.MD

## Deployment

Make sure to use Docker!!

`heroku stack:set container`

## Requirements

// TODO: Figure out how to add these 2 to a normal ts server on heroku
https://devcenter.heroku.com/articles/using-multiple-buildpacks-for-an-app
// Prob just write a shitty buildpack that installs these 2
// And then use normal Nodejs buildpack by heroku


- jq
- foundry

- yarn
- node
- 2 postgres databases (see .env) | Use Heroku or a decent one else you will get random errors!


## Setting up Prisma

Get the 2 DBs

Then do

`npx prisma db push`

Then

`npx prisma migrate dev --name init` <- This reverts for me but the system seems to work


Try
`npx prisma studio`

To see if it somewhat works

Follow this guide and cross your fingers
https://www.prisma.io/docs/orm/prisma-migrate/getting-started#adding-prisma-migrate-to-an-existing-project


## Schema Notes

NOTE: just the fields that have comments

model Job {
  status   String // `created` | `running` | `completed`
}

model ABIData {
  id Int    @id @default(autoincrement()) // Basically unused
  identifier String // orgName_repoName_branch // Real identifier
}



# Orgs and Users

Orgs are used for billings / Credits as well as Global Settings

Heroic accounts will load their info exclusively in the Org
Legendary accounts will load their info also in the User, as to customize that data

Every user belongs to one Org

Super Admin can change the Org that an user Belong To

Super Admin can delete an Org but they first must delete all Users or move them to another org


# User Onboarding

A user login is tied to GH Token

We don't really need to store them until we need to assign them to an org

So the UI can just use GH to login

Then secretely ping

`GET /organizations/my`

Which will check if the user has a Pro or not account

If they have Pro, we can show Pro or smth

If they don't have Pro, we can show Free or smth

If they don't have an Organization, we can prompt them to create one when necessary

--------

You don't have an invite, but you can try Recon for Free -> Activate Free Account

-> We need an Org when we start building ABI
-> We do not need an Org for Installs
-> We need an Org to Queue an Track Jobs


# Heroku usage

-> To deploy custom branch

-> Set Heroku to use the Container stack! Or the system will not work




# Local Smee

Use Smee to forward webhooks
`
 smee -u https://smee.io/y4i1WPpr9NhVVCsw -P /webhooks -p 6969
`

`
-P for path
-p for port
`
